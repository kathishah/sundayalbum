# Sunday Album - Local Processing Engine

Free tool to digitize physical photo album pages into clean individual digital photos.

This is the **Phase 1** implementation with project scaffold, image loading (HEIC + DNG), and basic CLI.

## Setup

### 1. Install System Dependencies (macOS with Homebrew)

```bash
brew install opencv libheif libraw imagemagick
```

### 2. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate  # On Windows
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
# or for development
pip install -e ".[dev]"
```

### 4. Configure Environment Variables

```bash
cp .env.example .env
# Edit .env and add your API keys if needed
```

### 5. Add Test Images

Place your HEIC and DNG test images in the `test-images/` directory.
See `test-images/README.md` for expected file names.

## Usage

### Process a Single Image

```bash
python -m src.cli process test-images/IMG_cave_normal.HEIC --output ./output/ --debug
```

### Process All HEIC Files in Batch

```bash
python -m src.cli process test-images/ --output ./output/ --batch --filter "*.HEIC" --debug
```

### Process DNG File

```bash
python -m src.cli process test-images/IMG_cave_prores.DNG --output ./output/ --debug
```

## Project Structure

```
sundayalbum/
├── src/                        # Source code
│   ├── preprocessing/          # Image loading and normalization
│   ├── page_detection/         # (Phase 2)
│   ├── glare/                  # (Phase 3-5)
│   ├── photo_detection/        # (Phase 6)
│   ├── geometry/               # (Phase 7)
│   ├── color/                  # (Phase 8)
│   ├── ai/                     # (Phase 9)
│   ├── utils/                  # Debug and utilities
│   ├── pipeline.py             # Main pipeline orchestrator
│   └── cli.py                  # CLI interface
├── tests/                      # Tests
├── test-images/                # Test images (gitignored)
├── output/                     # Processed output (gitignored)
├── debug/                      # Debug visualizations (gitignored)
└── docs/                       # Documentation

```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_loader.py -v

# Run with verbose output
pytest tests/test_loader.py -v -s
```

## Development

This project follows strict typing and code quality standards:

```bash
# Type checking
mypy src/

# Linting
ruff check src/

# Auto-format
ruff format src/
```

## Phase 1 Complete ✓

- [x] Project scaffold with pyproject.toml and requirements.txt
- [x] Full directory structure with modules
- [x] HEIC image loading with pillow-heif
- [x] DNG/RAW image loading with rawpy
- [x] EXIF orientation handling
- [x] Image normalization and thumbnails
- [x] CLI with Click framework (process, check, compare commands)
- [x] Pipeline orchestrator with PipelineConfig
- [x] Debug output utilities
- [x] Comprehensive tests for image loading

## Next Steps

See `docs/PHASED_PLAN_Claude_Code.md` for Phase 2 and beyond.

## Documentation

- `CLAUDE.md` - Main project instructions and technical specifications
- `docs/PHASED_PLAN_Claude_Code.md` - Phased implementation plan
- `docs/PRD_Album_Digitizer.md` - Product requirements
- `docs/Implementation_Album_Digitizer.md` - Full implementation guide
- `docs/UI_Design_Album_Digitizer.md` - UI design (future phases)
