import hashlib
import json
import logging
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

import jwt
from django.conf import settings
from django.core.cache import cache
from jwt.exceptions import PyJWTError
from django.db.models import Q

from .models import Song


logger = logging.getLogger(__name__)
APPLE_API_ROOT = "https://api.music.apple.com/v1/catalog"
REQUEST_TIMEOUT = 8


class CatalogUnavailable(Exception):
	pass


class CatalogRateLimited(CatalogUnavailable):
	pass


class AppleMusicCatalog:
	def __init__(self):
		self.storefront = settings.APPLE_MUSIC_STOREFRONT

	def _developer_token(self):
		team_id = settings.APPLE_MUSIC_TEAM_ID
		key_id = settings.APPLE_MUSIC_KEY_ID
		cache_key = f"reelo_apple_music_token:{team_id}:{key_id}"
		token = cache.get(cache_key)
		if token:
			return token

		private_key = settings.APPLE_MUSIC_PRIVATE_KEY.replace("\\n", "\n")
		if not private_key and settings.APPLE_MUSIC_PRIVATE_KEY_PATH:
			key_path = Path(settings.APPLE_MUSIC_PRIVATE_KEY_PATH)
			if not key_path.is_absolute():
				key_path = settings.BASE_DIR / key_path
			try:
				private_key = key_path.read_text(encoding="utf-8")
			except OSError as error:
				raise CatalogUnavailable(
					"Apple Music signing key could not be read."
				) from error
		if not team_id or not key_id or not private_key:
			raise CatalogUnavailable(
				"Apple Music catalog credentials are incomplete."
			)

		now = int(time.time())
		try:
			token = jwt.encode(
				{"iss": team_id, "iat": now, "exp": now + 3600},
				private_key,
				algorithm="ES256",
				headers={"kid": key_id},
			)
		except (ValueError, TypeError, PyJWTError) as error:
			raise CatalogUnavailable(
				"Apple Music signing key is invalid."
			) from error
		cache.set(cache_key, token, timeout=3500)
		return token

	def _get_json(self, path, params):
		url = f"{APPLE_API_ROOT}/{self.storefront}/{path}?{urlencode(params)}"
		request = Request(
			url,
			headers={
				"Authorization": f"Bearer {self._developer_token()}",
				"Accept": "application/json",
			},
		)
		try:
			with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
				payload = json.loads(response.read())
		except HTTPError as error:
			if error.code == 429:
				raise CatalogRateLimited(
					"Apple Music temporarily rate-limited the catalog."
				) from error
			raise CatalogUnavailable(
				f"Apple Music catalog returned HTTP {error.code}."
			) from error
		except (
			URLError,
			TimeoutError,
			OSError,
			json.JSONDecodeError,
			UnicodeDecodeError,
		) as error:
			raise CatalogUnavailable(
				"Apple Music catalog could not be reached."
			) from error
		if not isinstance(payload, dict):
			raise CatalogUnavailable("Apple Music returned an invalid response.")
		return payload

	def search(self, query):
		payload = self._get_json(
			"search",
			{"term": query, "types": "songs", "limit": 25},
		)
		results = payload.get("results")
		songs = results.get("songs") if isinstance(results, dict) else None
		data = songs.get("data") if isinstance(songs, dict) else None
		return data if isinstance(data, list) else []

	def trending(self):
		payload = self._get_json(
			"charts",
			{"types": "songs", "limit": 25},
		)
		results = payload.get("results")
		charts = results.get("songs") if isinstance(results, dict) else None
		if not isinstance(charts, list) or not charts:
			return []
		data = charts[0].get("data") if isinstance(charts[0], dict) else None
		return data if isinstance(data, list) else []

	@staticmethod
	def _https_url(value):
		if not isinstance(value, str):
			return ""
		parsed = urlsplit(value)
		return value if parsed.scheme == "https" and parsed.netloc else ""

	def normalize(self, resource):
		attributes = resource.get("attributes")
		if not isinstance(attributes, dict):
			return None
		artwork = attributes.get("artwork")
		if not isinstance(artwork, dict):
			artwork = {}
		artwork_url = self._https_url(artwork.get("url", ""))
		if artwork_url:
			artwork_url = (
				artwork_url.replace("{w}", "300")
				.replace("{h}", "300")
				.replace("{f}", "jpg")
			)
		previews = attributes.get("previews") or attributes.get("previewAssets") or []
		if not isinstance(previews, list):
			previews = []
		preview_url = ""
		if previews and isinstance(previews[0], dict):
			preview_url = self._https_url(previews[0].get("url", ""))
		apple_id = resource.get("id")
		if not apple_id:
			return None
		apple_id = str(apple_id)
		try:
			duration = max(0, int(attributes.get("durationInMillis") or 0) // 1000)
		except (TypeError, ValueError):
			duration = 0
		return {
			"external_id": f"apple_music:{self.storefront}:{apple_id}"[:255],
			"title": str(attributes.get("name", "Untitled"))[:255],
			"artist": str(attributes.get("artistName", ""))[:255],
			"cover_url": artwork_url,
			"preview_url": preview_url,
			"duration": duration,
			"provider": "apple_music",
			"attribution": "Open in Apple Music",
			"attribution_url": self._https_url(attributes.get("url", "")),
		}


def _database_songs(query="", trending=False):
	songs = Song.objects.filter(
		Q(preview_url__gt="") | Q(rights_cleared=True) | Q(provider="apple_music")
	)
	if query:
		songs = songs.filter(
			Q(title__icontains=query) | Q(artist__icontains=query)
		)
	if trending:
		songs = songs.filter(is_trending=True)
	return list(songs[:25])


def _save_catalog_resources(resources, trending=False):
	catalog = AppleMusicCatalog()
	normalized = [
		catalog.normalize(resource)
		for resource in resources
		if isinstance(resource, dict)
	]
	songs = [item for item in normalized if item]
	if trending:
		Song.objects.filter(provider="apple_music", is_trending=True).update(
			is_trending=False
		)

	saved = []
	for item in songs[:25]:
		defaults = dict(item)
		if trending:
			defaults["is_trending"] = True
		song, _ = Song.objects.update_or_create(
			external_id=item["external_id"],
			defaults=defaults,
		)
		saved.append(song)
	return saved


def get_music_songs(query="", trending=False):
	configured = any(
		(
			settings.APPLE_MUSIC_TEAM_ID,
			settings.APPLE_MUSIC_KEY_ID,
			settings.APPLE_MUSIC_PRIVATE_KEY,
			settings.APPLE_MUSIC_PRIVATE_KEY_PATH,
		)
	)
	if not configured:
		return _database_songs(query=query, trending=trending), False

	cache_digest = hashlib.sha256(query.encode("utf-8")).hexdigest()
	cache_key = (
		f"reelo_apple_music_trending_{settings.APPLE_MUSIC_STOREFRONT}"
		if trending
		else f"reelo_apple_music_search_{settings.APPLE_MUSIC_STOREFRONT}_{cache_digest}"
	)
	cached_ids = cache.get(cache_key)
	if cached_ids is not None:
		songs_by_id = Song.objects.in_bulk(cached_ids)
		return [songs_by_id[song_id] for song_id in cached_ids if song_id in songs_by_id], False

	catalog = AppleMusicCatalog()
	try:
		resources = catalog.trending() if trending else catalog.search(query)
		songs = _save_catalog_resources(resources, trending=trending)
		cache.set(cache_key, [song.pk for song in songs], timeout=900 if trending else 300)
		return songs, False
	except CatalogUnavailable as error:
		logger.warning("Music catalog unavailable (%s).", error)
		return (
			_database_songs(query=query, trending=trending),
			True,
		)
