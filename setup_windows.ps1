Write-Host "Setting up Speech to Indian Sign Language Converter" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# -----------------------------
# 0) Check Python installation
# -----------------------------
Write-Host "Checking Python installation..." -ForegroundColor Cyan
try {
    $pythonVersionOutput = & python --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Python not found."
    }
    Write-Host "Python version: $pythonVersionOutput" -ForegroundColor Green

    # Extract major.minor
    $pythonVersion = ($pythonVersionOutput -split " ")[1]
    $majorMinor = $pythonVersion -replace "(\d+\.\d+).*",'$1'

    if ($majorMinor -ne "3.11") {
        Write-Warning "Recommended Python version is 3.11, but you are using $pythonVersion"
    }
} catch {
    Write-Host "Python not found. Please install Python 3.11 from https://www.python.org/downloads/release/python-3110/" -ForegroundColor Red
    exit 1
}

# -----------------------------
# 1) Upgrade pip
# -----------------------------
Write-Host "Upgrading pip..." -ForegroundColor Cyan
python -m pip install --upgrade pip

# -----------------------------
# 2) Install Python dependencies
# -----------------------------
if (Test-Path "requirements.txt") {
    Write-Host "Installing Python dependencies..." -ForegroundColor Cyan
    pip install -r requirements.txt
} else {
    Write-Host "requirements.txt not found. Skipping Python dependency installation." -ForegroundColor Yellow
}

# -----------------------------
# 3) Download NLTK data
# -----------------------------
Write-Host "Checking NLTK data..." -ForegroundColor Cyan
$NLTK_DIR = Join-Path $env:APPDATA "nltk_data"

if (-not (Test-Path $NLTK_DIR)) {
    Write-Host "Downloading NLTK stopwords, wordnet, omw-1.4..." -ForegroundColor Cyan
    python -c "import nltk; nltk.download('stopwords'); nltk.download('wordnet'); nltk.download('omw-1.4')"
} else {
    Write-Host "NLTK data already exists at $NLTK_DIR. Skipping download." -ForegroundColor Green
}

# -----------------------------
# 4) Download Stanford Parser
# -----------------------------
$StanfordFolder = "stanford-parser-full"
$StanfordZip    = "stanford-parser-4.2.0.zip"
$StanfordUrl    = "https://downloads.cs.stanford.edu/nlp/software/stanford-parser-4.2.0.zip"

if (-not (Test-Path $StanfordFolder)) {
    Write-Host "Downloading Stanford Parser..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri $StanfordUrl -OutFile $StanfordZip
    Expand-Archive -Path $StanfordZip -DestinationPath .
    if (Test-Path "stanford-parser-full-2020-11-17") {
        Move-Item "stanford-parser-full-2020-11-17" $StanfordFolder
    }
    Remove-Item $StanfordZip
    Write-Host "Stanford Parser setup complete." -ForegroundColor Green
} else {
    Write-Host "Stanford Parser already exists. Skipping download." -ForegroundColor Green
}

# -----------------------------
# 4a) Verify stanford-parser.jar exists
# -----------------------------
$StanfordJar = Join-Path $StanfordFolder "stanford-parser.jar"
if (-not (Test-Path $StanfordJar)) {
    Write-Host "ERROR: stanford-parser.jar not found in $StanfordFolder" -ForegroundColor Red
    Write-Host "Download may have failed. Please delete $StanfordFolder and re-run this script." -ForegroundColor Red
    exit 1
} else {
    Write-Host "Verified: stanford-parser.jar exists in $StanfordFolder" -ForegroundColor Green
}

# -----------------------------
# 5) Check Java installation & version
# -----------------------------
Write-Host "Checking Java installation..." -ForegroundColor Cyan
try {
    $javaVersionOutput = & java -version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Java not found."
    }
    Write-Host "Java version output: $javaVersionOutput" -ForegroundColor Green

    # Extract version number (e.g., "17.0.8")
    $javaVersion = ($javaVersionOutput -split '"')[1]
    $majorJava = ($javaVersion -split '\.')[0]

    if ([int]$majorJava -lt 11) {
        Write-Host "ERROR: Java version $javaVersion detected. Stanford Parser requires Java 11 or higher." -ForegroundColor Red
        Write-Host "Please install Java 11+ from: https://www.oracle.com/java/technologies/javase/jdk11-archive-downloads.html" -ForegroundColor Yellow
        exit 1
    } else {
        Write-Host "Java version check passed (>= 11)." -ForegroundColor Green
    }
} catch {
    Write-Host "Java not found. Please install Java and try again." -ForegroundColor Red
    Write-Host "Download from: https://www.oracle.com/java/technologies/javase/jdk11-archive-downloads.html" -ForegroundColor Yellow
    exit 1
}

# -----------------------------
# 6) Check FFmpeg installation & version (auto-install if missing)
# -----------------------------
Write-Host "Checking FFmpeg installation..." -ForegroundColor Cyan
$ffmpegPath = "C:\ffmpeg"
$ffmpegBin  = Join-Path $ffmpegPath "bin\ffmpeg.exe"

if (-not (Test-Path $ffmpegBin)) {
    Write-Host "FFmpeg not found. Installing to $ffmpegPath..." -ForegroundColor Yellow

    # Download latest FFmpeg release (static build from gyan.dev mirror)
    $ffmpegZip = "ffmpeg-release-full.7z"
    $ffmpegUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-full.7z"

    Invoke-WebRequest -Uri $ffmpegUrl -OutFile $ffmpegZip

    # Ensure 7-Zip is installed
    if (-not (Get-Command 7z.exe -ErrorAction SilentlyContinue)) {
        Write-Host "7-Zip is required to extract FFmpeg. Please install it from https://www.7-zip.org/" -ForegroundColor Red
        exit 1
    }

    # Extract into C:\ffmpeg
    if (Test-Path $ffmpegPath) { Remove-Item -Recurse -Force $ffmpegPath }
    mkdir $ffmpegPath | Out-Null
    7z x $ffmpegZip "-o$ffmpegPath" -y | Out-Null
    Remove-Item $ffmpegZip

    # Some builds unpack into a subfolder like ffmpeg-2025... → flatten
    $subfolders = Get-ChildItem $ffmpegPath | Where-Object { $_.PSIsContainer }
    if ($subfolders.Count -eq 1) {
        Move-Item "$($subfolders[0].FullName)\*" $ffmpegPath -Force
        Remove-Item $subfolders[0].FullName -Recurse -Force
    }

    # Add C:\ffmpeg\bin to PATH (User-level, permanent)
    $envPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    if ($envPath -notlike "*C:\ffmpeg\bin*") {
        [System.Environment]::SetEnvironmentVariable("Path", $envPath + ";C:\ffmpeg\bin", "User")
        Write-Host "Added C:\ffmpeg\bin to PATH. Please restart your terminal for changes to apply." -ForegroundColor Yellow
    }

    Write-Host "FFmpeg installed successfully at $ffmpegBin" -ForegroundColor Green
}

# Verify FFmpeg version (fixed parser)
try {
    $ffmpegVersionOutput = & $ffmpegBin -version 2>&1
    $firstLine = $ffmpegVersionOutput[0]
    Write-Host "FFmpeg version output: $firstLine" -ForegroundColor Green

    # Extract after "ffmpeg version"
    $versionToken = ($firstLine -split " ")[2]

    if ($versionToken -match "^\d{4}-\d{2}-\d{2}") {
        # Date-based build (e.g., 2024-06-13 → always new enough)
        Write-Host "Detected date-based FFmpeg build ($versionToken). Assuming it's >= 4.0." -ForegroundColor Green
    }
    elseif ($versionToken -match "^\d+(\.\d+)+$") {
        # Standard version like 4.4.1
        $majorMinor = $versionToken -replace "(\d+\.\d+).*",'$1'
        if ([version]$majorMinor -lt [version]"4.0") {
            Write-Host "ERROR: FFmpeg version $versionToken detected. Please install FFmpeg 4.0 or higher." -ForegroundColor Red
            exit 1
        } else {
            Write-Host "FFmpeg version check passed (>= 4.0)." -ForegroundColor Green
        }
    }
    else {
        Write-Warning "Could not parse FFmpeg version. Proceeding cautiously..."
    }
} catch {
    Write-Host "FFmpeg installation failed. Please install manually from https://ffmpeg.org/download.html" -ForegroundColor Red
    exit 1
}

# -----------------------------
# 7) Setup complete
# -----------------------------
Write-Host "`nSetup complete! Run the application with: python app.py" -ForegroundColor Green
Write-Host "Then open http://127.0.0.1:5000 in your browser." -ForegroundColor Green
