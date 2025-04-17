// DOM Elements
const textForm = document.getElementById('textForm');
const audioUploadForm = document.getElementById('audioUploadForm');
const startRecordingBtn = document.getElementById('startRecording');
const stopRecordingBtn = document.getElementById('stopRecording');
const recordingStatus = document.getElementById('recordingStatus');
const recordingTimer = document.getElementById('recordingTimer');
const loadingOverlay = document.getElementById('loadingOverlay');
const resultsSection = document.getElementById('resultsSection');
const englishTextResult = document.getElementById('englishTextResult');
const islTextResult = document.getElementById('islTextResult');
const islVideo = document.getElementById('islVideo');

// Audio recording variables
let mediaRecorder;
let audioChunks = [];
let recordingStartTime;
let recordingTimerInterval;

// Event Listeners
textForm.addEventListener('submit', handleTextSubmit);
audioUploadForm.addEventListener('submit', handleAudioUploadSubmit);
startRecordingBtn.addEventListener('click', startRecording);
stopRecordingBtn.addEventListener('click', stopRecording);

// Handle text input submission
function handleTextSubmit(e) {
    e.preventDefault();
    
    const textInput = document.getElementById('textInput').value.trim();
    if (!textInput) return;
    
    showLoading();
    
    // Create form data
    const formData = new FormData();
    formData.append('text', textInput);
    
    // Send request to server
    fetch('/process_text', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        if (data.status === 'success') {
            displayResults(data);
        } else {
            showError('Failed to process text. Please try again.');
        }
    })
    .catch(error => {
        hideLoading();
        showError('An error occurred. Please try again.');
        console.error('Error:', error);
    });
}

// Handle audio file upload submission
function handleAudioUploadSubmit(e) {
    e.preventDefault();
    
    const audioFile = document.getElementById('audioFileInput').files[0];
    if (!audioFile) return;
    
    showLoading();
    
    // Create form data
    const formData = new FormData();
    formData.append('audio', audioFile);
    
    // Send request to server
    fetch('/process_audio', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        if (data.status === 'success') {
            displayResults(data);
        } else {
            showError('Failed to process audio. Please try again.');
        }
    })
    .catch(error => {
        hideLoading();
        showError('An error occurred. Please try again.');
        console.error('Error:', error);
    });
}

// Start audio recording
function startRecording() {
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            // Show recording UI
            startRecordingBtn.classList.add('d-none');
            stopRecordingBtn.classList.remove('d-none');
            recordingStatus.textContent = 'Recording...';
            recordingTimer.classList.remove('d-none');
            
            // Initialize media recorder
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            
            // Start recording
            mediaRecorder.start();
            startRecordingBtn.classList.add('recording');
            
            // Update timer
            recordingStartTime = Date.now();
            updateRecordingTimer();
            recordingTimerInterval = setInterval(updateRecordingTimer, 1000);
            
            // Event handlers
            mediaRecorder.addEventListener('dataavailable', event => {
                audioChunks.push(event.data);
            });
            
            mediaRecorder.addEventListener('stop', () => {
                // Clean up
                clearInterval(recordingTimerInterval);
                stream.getTracks().forEach(track => track.stop());
                
                // Process the recorded audio
                processRecordedAudio();
            });
        })
        .catch(error => {
            showError('Could not access microphone. Please check your permissions.');
            console.error('Error accessing media devices:', error);
        });
}

// Stop audio recording
function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        recordingStatus.textContent = 'Processing audio...';
    }
}

// Update recording timer display
function updateRecordingTimer() {
    const elapsedSeconds = Math.floor((Date.now() - recordingStartTime) / 1000);
    const minutes = Math.floor(elapsedSeconds / 60).toString().padStart(2, '0');
    const seconds = (elapsedSeconds % 60).toString().padStart(2, '0');
    recordingTimer.textContent = `${minutes}:${seconds}`;
}

// Process recorded audio
function processRecordedAudio() {
    showLoading();
    
    // Create audio blob and form data
    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
    const formData = new FormData();
    formData.append('audio', audioBlob);
    
    // Send request to server
    fetch('/record_audio', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        
        // Reset recording UI
        startRecordingBtn.classList.remove('d-none');
        stopRecordingBtn.classList.add('d-none');
        recordingStatus.textContent = 'Click the microphone to start recording';
        recordingTimer.classList.add('d-none');
        startRecordingBtn.classList.remove('recording');
        
        if (data.status === 'success') {
            displayResults(data);
        } else {
            showError('Failed to process recording. Please try again.');
        }
    })
    .catch(error => {
        hideLoading();
        
        // Reset recording UI
        startRecordingBtn.classList.remove('d-none');
        stopRecordingBtn.classList.add('d-none');
        recordingStatus.textContent = 'Click the microphone to start recording';
        recordingTimer.classList.add('d-none');
        startRecordingBtn.classList.remove('recording');
        
        showError('An error occurred. Please try again.');
        console.error('Error:', error);
    });
}

// Display results
function displayResults(data) {
    englishTextResult.textContent = data.english_text || 'No text recognized';
    islTextResult.textContent = data.isl_text || 'No ISL conversion available';
    
    if (data.video_path) {
        islVideo.src = `/static/${data.video_path}`;
        islVideo.load();
    } else {
        islVideo.src = '';
    }
    
    resultsSection.classList.remove('d-none');
    
    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth' });
}

// Show loading overlay
function showLoading() {
    loadingOverlay.classList.remove('d-none');
}

// Hide loading overlay
function hideLoading() {
    loadingOverlay.classList.add('d-none');
}

// Show error message
function showError(message) {
    // Create toast notification
    const toastContainer = document.createElement('div');
    toastContainer.className = 'position-fixed bottom-0 end-0 p-3';
    toastContainer.style.zIndex = '1060';
    
    const toastContent = `
        <div class="toast align-items-center text-white bg-danger border-0" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas fa-exclamation-circle me-2"></i>${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;
    
    toastContainer.innerHTML = toastContent;
    document.body.appendChild(toastContainer);
    
    // Initialize and show the toast
    const toastElement = toastContainer.querySelector('.toast');
    const toast = new bootstrap.Toast(toastElement, { delay: 5000 });
    toast.show();
    
    // Remove toast container after hiding
    toastElement.addEventListener('hidden.bs.toast', () => {
        document.body.removeChild(toastContainer);
    });
}