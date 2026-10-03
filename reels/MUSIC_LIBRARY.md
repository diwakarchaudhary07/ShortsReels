# Reelo Music Library

Reelo uses the existing `Song` model as a normalized catalog cache. Posts,
Reels, and Stories keep a nullable foreign key to a song; catalog metadata and
preview files are not copied into user media. The picker and authenticated
JSON endpoints are Reelo-branded. Provider-required attribution is shown on
each song result.

## Catalog and rights

The optional first catalog adapter is Apple Music. It uses the India storefront
by default for song search and Apple song charts for the trending tab. Search
results and chart entries are normalized into `Song` records and cached in the
database; preview URLs and Apple Music links are stored as metadata only.
Preview availability depends on the track and storefront. When Apple is not
configured, the same endpoints search/traverse the Reelo-curated database.

Apple catalog access and preview URLs do **not** grant Reelo the right to
synchronize a recording or composition into a user's uploaded video. Reelo does
not download catalog audio or combine previews with Posts, Reels, or Stories.
Obtain separate rights-holder clearance for audiovisual/synchronization use,
territories, monetization, and public distribution before enabling any such
feature. `rights_cleared` is only for tracks Reelo has documented rights to use;
only those tracks may use a Reelo-hosted `audio_file` preview. Do not upload
copyrighted audio without those rights.

Apple Music developer documentation:

- [Apple Music API](https://developer.apple.com/musickit/)
- [Search catalog resources](https://developer.apple.com/documentation/applemusicapi/search-for-catalog-resources-(by-type))
- [Catalog charts](https://developer.apple.com/documentation/applemusicapi/get-a-catalog-chart)
- [Developer tokens](https://developer.apple.com/documentation/applemusicapi/generating-developer-tokens)

Apple access has no public per-request price or fixed numeric quota stated in
the API references above. Configure for Apple responses and `429` rate limits;
verify current account, access, terms, storefront coverage, and branding rules
with Apple before production launch. Apple is a discovery and compliant preview
candidate, not a commercial soundtrack license or a promise of complete Hindi
or Indian music coverage. Reelo should not describe third-party popularity as
real-time; Apple charts are a provider-provided chart snapshot.

## Configure Apple Music

1. Create an Apple Music media identifier and a MusicKit private key in the
   Apple Developer account.
2. Copy `reels/.env.example` to `reels/.env`.
3. Set `APPLE_MUSIC_TEAM_ID`, `APPLE_MUSIC_KEY_ID`,
   `APPLE_MUSIC_PRIVATE_KEY_PATH`, and optionally `APPLE_MUSIC_STOREFRONT`.
   The default storefront is `in`. Put the `.p8` file under `reels/secrets/`;
   that directory is ignored by Git. Never put credentials in a template,
   static JavaScript, or committed settings file.
4. Install project dependencies from the repository root:

   ```powershell
   pip install -r requirements.txt
   ```

Without Apple credentials, the music endpoints remain available from
rights-cleared or preview-URL catalog entries managed in Django admin. Catalog
timeouts, malformed responses, and rate limits fall back to locally cached
songs; the API marks this degraded result in its JSON response.

## Endpoints and composer integration

- `GET /api/music/search/?q=...` searches the Apple India catalog when
  configured, otherwise searches the Reelo cache.
- `GET /api/music/trending/` returns Apple song charts when configured,
  otherwise Reelo songs marked trending in admin.
- `GET /api/music/<song-id>/` returns a cached song.

All endpoints require a logged-in user. The browser communicates only with
these same-origin Django URLs; Apple developer tokens are generated and sent by
the server. Search terms are limited to 100 characters, and results are capped
at 25 songs.

The shared Reelo picker is included by the base template and used from Post,
Reel, and Story composers. Stories are new in this project and expire 24 hours
after creation. Reelo-hosted audio previews are only served in the picker for
tracks marked `rights_cleared`.

Apply schema changes and run tests from the Django project directory:

```powershell
python manage.py migrate
python manage.py check
python manage.py test reelo
```
