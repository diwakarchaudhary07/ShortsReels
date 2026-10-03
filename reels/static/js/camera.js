(() => {
  const dialog = document.querySelector("[data-camera-dialog]");
  if (!dialog) return;

  const liveVideo = dialog.querySelector("[data-camera-live]");
  const capturedVideo = dialog.querySelector("[data-camera-captured]");
  const capturedPhoto = dialog.querySelector("[data-camera-photo]");
  const errorPanel = dialog.querySelector("[data-camera-error]");
  const errorMessage = dialog.querySelector("[data-camera-error-message]");
  const controls = dialog.querySelector("[data-camera-controls]");
  const review = dialog.querySelector("[data-camera-review]");
  const status = dialog.querySelector("[data-camera-status]");
  const captureButton = dialog.querySelector("[data-camera-capture]");
  const flipButton = dialog.querySelector("[data-camera-flip]");
  const useButton = dialog.querySelector("[data-camera-use]");
  const modeButtons = [...dialog.querySelectorAll("[data-camera-mode]")];

  let stream = null;
  let recorder = null;
  let recordedChunks = [];
  let facingMode = "environment";
  let activeMode = "photo";
  let activeTrigger = null;
  let capturedBlob = null;
  let previewUrl = "";
  let requestToken = 0;
  let maxDurationTimer = 0;

  const stopStream = () => {
    const currentStream = stream;
    stream = null;
    liveVideo.srcObject = null;
    if (currentStream) {
      currentStream.getTracks().forEach((track) => track.stop());
    }
  };

  const clearPreview = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = "";
    capturedBlob = null;
    capturedPhoto.removeAttribute("src");
    capturedVideo.pause();
    capturedVideo.removeAttribute("src");
    capturedVideo.load();
  };

  const cleanupCamera = () => {
    requestToken += 1;
    window.clearTimeout(maxDurationTimer);
    if (recorder && recorder.state !== "inactive") recorder.stop();
    recorder = null;
    recordedChunks = [];
    stopStream();
    clearPreview();
    review.hidden = true;
    controls.hidden = false;
    errorPanel.hidden = true;
    status.textContent = "";
    captureButton.classList.remove("is-recording");
  };

  const showError = (error) => {
    const name = error?.name;
    let message = "We couldn't start your camera. Check your camera and try again.";
    if (!window.isSecureContext) {
      message = "Camera access requires HTTPS. Open Reelo over a secure connection.";
    } else if (!navigator.mediaDevices?.getUserMedia) {
      message = "This browser doesn't support live camera access. Try a recent browser or upload a file instead.";
    } else if (name === "NotAllowedError" || name === "SecurityError") {
      message = "Camera access is blocked. Allow camera permission for Reelo in your browser settings, then try again.";
    } else if (name === "NotFoundError" || name === "DevicesNotFoundError") {
      message = "No camera was found on this device. Connect a camera or upload a file instead.";
    } else if (name === "NotReadableError" || name === "TrackStartError") {
      message = "Your camera is unavailable or being used by another app. Close that app and try again.";
    } else if (name === "OverconstrainedError") {
      message = "That camera isn't available. Try flipping the camera.";
    }
    errorMessage.textContent = message;
    errorPanel.hidden = false;
    controls.hidden = true;
    review.hidden = true;
    status.textContent = "";
  };

  const startCamera = async () => {
    stopStream();
    const thisRequest = ++requestToken;
    errorPanel.hidden = true;
    controls.hidden = false;
    review.hidden = true;
    status.textContent = "Requesting camera permission...";
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      showError({ name: window.isSecureContext ? "NotSupportedError" : "SecurityError" });
      return;
    }
    try {
      const newStream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: { ideal: facingMode },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
      });
      if (thisRequest !== requestToken || !dialog.open) {
        newStream.getTracks().forEach((track) => track.stop());
        return;
      }
      stream = newStream;
      newStream.getTracks().forEach((track) => {
        track.addEventListener("ended", () => {
          if (stream === newStream && dialog.open) {
            stopStream();
            showError({ name: "NotReadableError" });
          }
        });
      });
      liveVideo.srcObject = stream;
      liveVideo.hidden = false;
      capturedPhoto.hidden = true;
      capturedVideo.hidden = true;
      await liveVideo.play();
      status.textContent = "Camera ready";
    } catch (error) {
      if (thisRequest === requestToken) {
        stopStream();
        showError(error);
      }
    }
  };

  const setMode = (mode) => {
    activeMode = mode;
    if (activeTrigger) {
      const target = mode === "photo"
        ? activeTrigger.dataset.cameraPhotoTarget
        : activeTrigger.dataset.cameraVideoTarget;
      if (target) activeTrigger.dataset.cameraTarget = target;
    }
    modeButtons.forEach((button) => {
      const selected = button.dataset.cameraMode === mode;
      button.classList.toggle("is-active", selected);
      button.setAttribute("aria-pressed", String(selected));
      button.disabled = recorder?.state === "recording";
    });
    flipButton.disabled = recorder?.state === "recording";
    captureButton.setAttribute(
      "aria-label",
      mode === "photo" ? "Capture photo" : "Start video recording",
    );
    status.textContent = "";
  };

  const showCapturedPreview = (blob) => {
    capturedBlob = blob;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(blob);
    stopStream();
    liveVideo.hidden = true;
    controls.hidden = true;
    review.hidden = false;
    capturedPhoto.hidden = activeMode !== "photo";
    capturedVideo.hidden = activeMode !== "video";
    if (activeMode === "photo") {
      capturedPhoto.src = previewUrl;
      useButton.textContent = "Use photo";
    } else {
      capturedVideo.src = previewUrl;
      capturedVideo.load();
      useButton.textContent = "Use video";
    }
    status.textContent = "";
  };

  const capturePhoto = () => {
    if (!stream || !liveVideo.videoWidth || !liveVideo.videoHeight) {
      status.textContent = "The camera is still starting. Please wait a moment.";
      return;
    }
    const canvas = document.createElement("canvas");
    canvas.width = liveVideo.videoWidth;
    canvas.height = liveVideo.videoHeight;
    const captureRequest = requestToken;
    const context = canvas.getContext("2d");
    if (!context) {
      status.textContent = "This browser couldn't capture a photo.";
      return;
    }
    context.drawImage(liveVideo, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (!dialog.open || captureRequest !== requestToken) return;
      if (!blob) {
        status.textContent = "The photo couldn't be captured. Please try again.";
        return;
      }
      showCapturedPreview(blob);
    }, "image/jpeg", 0.92);
  };

  const stopRecording = () => {
    window.clearTimeout(maxDurationTimer);
    if (recorder && recorder.state === "recording") recorder.stop();
  };

  const startRecording = () => {
    if (!stream) {
      status.textContent = "The camera is still starting. Please wait a moment.";
      return;
    }
    if (!window.MediaRecorder) {
      status.textContent = "Video recording isn't supported in this browser. Try a recent browser or upload a video.";
      return;
    }
    const supportedType = [
      "video/mp4",
      "video/webm;codecs=vp9",
      "video/webm;codecs=vp8",
      "video/webm",
    ].find((type) => MediaRecorder.isTypeSupported(type));
    try {
      const currentRecorder = supportedType
        ? new MediaRecorder(stream, { mimeType: supportedType })
        : new MediaRecorder(stream);
      recorder = currentRecorder;
      recordedChunks = [];
      currentRecorder.addEventListener("dataavailable", (event) => {
        if (currentRecorder !== recorder) return;
        if (event.data.size) recordedChunks.push(event.data);
      });
      currentRecorder.addEventListener("error", () => {
        if (currentRecorder !== recorder) return;
        status.textContent = "Recording failed. Please try again.";
        captureButton.classList.remove("is-recording");
        captureButton.setAttribute("aria-label", "Start video recording");
        modeButtons.forEach((button) => (button.disabled = false));
        flipButton.disabled = false;
      });
      currentRecorder.addEventListener("stop", () => {
        if (!dialog.open || currentRecorder !== recorder) return;
        if (!recordedChunks.length) {
          recorder = null;
          captureButton.classList.remove("is-recording");
          captureButton.setAttribute("aria-label", "Start video recording");
          modeButtons.forEach((button) => (button.disabled = false));
          flipButton.disabled = false;
          status.textContent = "No video was recorded. Please try again.";
          return;
        }
        const blob = new Blob(recordedChunks, {
          type: currentRecorder.mimeType || "video/webm",
        });
        showCapturedPreview(blob);
        recorder = null;
        recordedChunks = [];
        captureButton.classList.remove("is-recording");
        captureButton.setAttribute("aria-label", "Start video recording");
        modeButtons.forEach((button) => (button.disabled = false));
        flipButton.disabled = false;
      });
      currentRecorder.start();
      captureButton.classList.add("is-recording");
      captureButton.setAttribute("aria-label", "Stop video recording");
      modeButtons.forEach((button) => (button.disabled = true));
      flipButton.disabled = true;
      status.textContent = "Recording · tap the red button to stop (max 60 seconds)";
      maxDurationTimer = window.setTimeout(stopRecording, 60_000);
    } catch (error) {
      status.textContent = "This device couldn't start video recording. Try another browser or upload a video.";
    }
  };

  const acceptCapture = () => {
    const selector = activeTrigger?.dataset.cameraTarget;
    const input = selector ? document.querySelector(selector) : null;
    if (!(input instanceof HTMLInputElement) || !capturedBlob) {
      errorMessage.textContent = "The captured media couldn't be added. Close the camera and try again.";
      errorPanel.hidden = false;
      return;
    }

    const type = capturedBlob.type || (activeMode === "photo" ? "image/jpeg" : "video/webm");
    const extension = activeMode === "photo"
      ? "jpg"
      : type.includes("mp4") ? "mp4" : "webm";
    const file = new File(
      [capturedBlob],
      `reelo-camera-${Date.now()}.${extension}`,
      { type },
    );
    const transfer = new DataTransfer();
    transfer.items.add(file);
    const otherSelector = activeMode === "photo"
      ? activeTrigger.dataset.cameraVideoTarget
      : activeTrigger.dataset.cameraPhotoTarget;
    const otherInput = otherSelector
      ? document.querySelector(otherSelector)
      : null;
    if (otherInput instanceof HTMLInputElement) otherInput.value = "";
    input.files = transfer.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
    dialog.close();
  };

  document.querySelectorAll("[data-camera-open]").forEach((trigger) => {
    trigger.addEventListener("click", () => {
      activeTrigger = trigger;
      clearPreview();
      errorPanel.hidden = true;
      capturedPhoto.hidden = true;
      capturedVideo.hidden = true;
      liveVideo.hidden = false;
      const allowedModes = (trigger.dataset.cameraModes || "photo,video")
        .split(",")
        .map((mode) => mode.trim());
      modeButtons.forEach((button) => {
        button.hidden = !allowedModes.includes(button.dataset.cameraMode);
      });
      setMode(allowedModes.includes("photo") ? "photo" : "video");
      dialog.showModal();
      startCamera();
    });
  });

  modeButtons.forEach((button) => {
    button.addEventListener("click", () => setMode(button.dataset.cameraMode));
  });
  captureButton.addEventListener("click", () => {
    if (activeMode === "photo") capturePhoto();
    else if (recorder?.state === "recording") stopRecording();
    else startRecording();
  });
  flipButton.addEventListener("click", async () => {
    facingMode = facingMode === "environment" ? "user" : "environment";
    await startCamera();
  });
  dialog.querySelector("[data-camera-close]").addEventListener("click", () => dialog.close());
  dialog.querySelector("[data-camera-retry]").addEventListener("click", startCamera);
  dialog.querySelector("[data-camera-retake]").addEventListener("click", () => {
    clearPreview();
    liveVideo.hidden = false;
    capturedPhoto.hidden = true;
    capturedVideo.hidden = true;
    startCamera();
  });
  useButton.addEventListener("click", acceptCapture);
  dialog.addEventListener("close", cleanupCamera);
  dialog.addEventListener("cancel", cleanupCamera);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && dialog.open) dialog.close();
  });
})();
