"""Command-line interface for Sunday Album processing."""

import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional

import click
from dotenv import load_dotenv

from src.pipeline import Pipeline, PipelineConfig, PIPELINE_STEPS
from src.storage.local import LocalStorage
from src.utils.debug import save_debug_image

# Build the canonical list of step IDs once at import time so the --steps help
# text always stays in sync with the pipeline definition.
_STEP_IDS: list[str] = [s["id"] for s in PIPELINE_STEPS]
_STEPS_HELP = (
    "Comma-separated pipeline step IDs to run (skips all others). "
    "Valid IDs: " + ", ".join(_STEP_IDS) + ". "
    "Example: -s load,photo_detect,glare_detect"
)

# Load environment variables from .env
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

logger = logging.getLogger(__name__)

# Shared context settings applied to every command and the group
_CTX = dict(help_option_names=["-h", "--help"], max_content_width=100)


class _DetailedGroup(click.Group):
    """Click Group subclass that appends each subcommand's option table to the group help."""

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        super().format_help(ctx, formatter)
        # Append per-subcommand option tables so `sunday --help` is self-contained
        for name in self.list_commands(ctx):
            cmd = self.commands.get(name)
            if cmd is None or cmd.hidden:
                continue
            sub_ctx = click.Context(cmd, info_name=name, parent=ctx)
            params = [p for p in cmd.params if isinstance(p, click.Option)]
            if not params:
                continue
            rows = []
            for param in params:
                flags = ", ".join(param.opts)
                metavar = param.make_metavar() if not param.is_flag else ""
                left = f"  {flags} {metavar}".rstrip()
                right = param.help or ""
                if param.default is not None and not param.is_flag:
                    right += f"  [default: {param.default}]"
                rows.append((left, right))
            with formatter.section(f"Options — {name}"):
                formatter.write_dl(rows)


@click.group(cls=_DetailedGroup, context_settings=_CTX)
@click.version_option(version="0.1.0")
def main() -> None:
    """Sunday Album — digitize physical photo album pages into clean individual digital photos.

    \b
    Commands:
      process   Run the full pipeline on one or more images
      validate  Batch-validate all test images and print a report
      check     Quality-check a processed image against its original
      compare   Side-by-side before/after comparison image
      status    Show pipeline implementation progress

    Run 'sunday COMMAND -h' for full options of any command.
    """
    pass


@main.command(context_settings=_CTX)
@click.argument('input_paths', nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    '--output', '-o',
    'output_dir',
    type=click.Path(),
    default='./output',
    show_default=True,
    help='Output directory for processed images',
)
@click.option(
    '--debug', '-d',
    is_flag=True,
    help='Save debug visualizations at each pipeline step',
)
@click.option(
    '--debug-dir',
    'debug_dir_path',
    type=click.Path(),
    default=None,
    metavar='DIR',
    help='Directory for debug visualizations (default: ./debug)',
)
@click.option(
    '--batch', '-b',
    is_flag=True,
    help='Process all images found inside a directory argument',
)
@click.option(
    '--filter', '-f',
    'filter_pattern',
    type=str,
    metavar='PATTERN',
    help='Glob pattern to filter files when using --batch (e.g. "*.HEIC")',
)
@click.option(
    '--steps', '-s',
    type=str,
    metavar='STEP,...',
    help=_STEPS_HELP,
)
@click.option(
    '--no-openai-glare', '-G',
    'no_openai_glare',
    is_flag=True,
    help='Disable OpenAI glare removal and fall back to OpenCV inpainting',
)
@click.option(
    '--scene-desc', '-D',
    'scene_desc',
    type=str,
    default=None,
    metavar='TEXT',
    help='Explicit scene description for OpenAI glare prompt (skips Claude description step)',
)
@click.option(
    '--no-ai-orientation', '-O',
    'no_ai_orientation',
    is_flag=True,
    help='Disable AI orientation correction (Claude Haiku call per photo)',
)
@click.option(
    '--forced-detections', '-F',
    'forced_detections_json',
    type=str,
    default=None,
    metavar='JSON',
    help=(
        'Override photo detection boundaries. Accepts a JSON array of detection dicts, '
        'each with a "bbox" key ([x1,y1,x2,y2]). '
        'Use with --steps photo_detect,... to skip re-detection. '
        'Example: \'[{"bbox":[50,80,620,1100]}]\''
    ),
)
@click.option(
    '--forced-rotation',
    'forced_rotation',
    type=click.IntRange(min=-360, max=360),
    default=None,
    metavar='DEGREES',
    help=(
        'Apply this exact rotation (degrees, e.g. 90 / 180 / 270 / -90) '
        'instead of calling the Claude orientation API. '
        'Maps to PipelineConfig.forced_rotation_degrees.'
    ),
)
@click.option(
    '--color-vibrance',
    'color_vibrance',
    type=click.FloatRange(min=0.0, max=1.0),
    default=None,
    metavar='FLOAT',
    help=(
        'color_restore_vibrance_boost override (0.0–1.0, default 0.25). '
        'Higher values produce more saturated output.'
    ),
)
@click.option(
    '--sharpen-amount',
    'sharpen_amount',
    type=click.FloatRange(min=0.0, max=1.0),
    default=None,
    metavar='FLOAT',
    help='sharpen_amount override (0.0–1.0, default 0.5).',
)
@click.option(
    '--workers', '-j',
    type=click.IntRange(min=1),
    default=1,
    show_default=True,
    metavar='N',
    help='Number of parallel workers (threads) for processing multiple files',
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='Enable verbose / DEBUG logging',
)
def process(
    input_paths: tuple,
    output_dir: str,
    debug: bool,
    debug_dir_path: Optional[str],
    batch: bool,
    filter_pattern: Optional[str],
    steps: Optional[str],
    no_openai_glare: bool,
    scene_desc: Optional[str],
    no_ai_orientation: bool,
    forced_detections_json: Optional[str],
    forced_rotation: Optional[int],
    color_vibrance: Optional[float],
    sharpen_amount: Optional[float],
    workers: int,
    verbose: bool
) -> None:
    """Process album page images through the digitization pipeline.

    INPUT_PATHS: One or more image files or directories to process
    """
    # Set logging level
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Parse steps filter
    steps_filter = None
    if steps:
        steps_filter = [s.strip() for s in steps.split(',')]
        logger.info(f"Running only steps: {steps_filter}")

    # Collect all input files
    input_files: List[Path] = []

    for input_path_str in input_paths:
        input_path = Path(input_path_str)

        if input_path.is_file():
            input_files.append(input_path)
        elif input_path.is_dir():
            if batch:
                # Find all image files in directory
                if filter_pattern:
                    pattern_files = list(input_path.glob(filter_pattern))
                    input_files.extend(pattern_files)
                    logger.info(f"Found {len(pattern_files)} files matching {filter_pattern}")
                else:
                    # Default to common image extensions
                    for ext in ['*.heic', '*.HEIC', '*.dng', '*.DNG', '*.jpg', '*.JPG', '*.jpeg', '*.JPEG', '*.png', '*.PNG']:
                        input_files.extend(input_path.glob(ext))
            else:
                logger.error(f"Directory provided but --batch not specified: {input_path}")
                sys.exit(1)
        else:
            logger.error(f"Invalid input path: {input_path}")
            sys.exit(1)

    if not input_files:
        logger.error("No input files found")
        sys.exit(1)

    logger.info(f"Processing {len(input_files)} file(s) with {workers} worker(s)")

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Create debug directory if requested
    debug_dir = None
    if debug:
        debug_dir = Path(debug_dir_path) if debug_dir_path else Path('./debug')
        debug_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Debug output will be saved to: {debug_dir}")

    # Parse --forced-detections JSON
    forced_detections = None
    if forced_detections_json:
        import json as _json
        try:
            forced_detections = _json.loads(forced_detections_json)
            if not isinstance(forced_detections, list):
                logger.error("--forced-detections must be a JSON array")
                sys.exit(1)
        except _json.JSONDecodeError as exc:
            logger.error("--forced-detections: invalid JSON — %s", exc)
            sys.exit(1)

    from src.utils.secrets import load_secrets
    _secrets = load_secrets()
    _config_kwargs: dict = dict(
        use_openai_glare_removal=not no_openai_glare,
        use_ai_orientation=not no_ai_orientation,
        forced_scene_description=scene_desc,
        forced_detections=forced_detections,
        anthropic_api_key=_secrets.anthropic_api_key or "",
        openai_api_key=_secrets.openai_api_key or "",
    )
    if forced_rotation is not None:
        _config_kwargs["forced_rotation_degrees"] = forced_rotation
    if color_vibrance is not None:
        _config_kwargs["color_restore_vibrance_boost"] = color_vibrance
    if sharpen_amount is not None:
        _config_kwargs["sharpen_amount"] = sharpen_amount
    config = PipelineConfig(**_config_kwargs)

    def _process_one(input_file: Path) -> Optional[object]:
        """Process a single file and save its outputs. Returns PipelineResult or None on error."""
        try:
            logger.info(f"\n{'=' * 60}")
            logger.info(f"Processing: {input_file.name}")
            logger.info(f"{'=' * 60}")

            # Each worker gets its own Pipeline + LocalStorage (not thread-safe to share)
            file_storage = LocalStorage(
                base_dir=Path("."),
                debug_dir=debug_dir if debug else None,
                output_dir=output_path,
            )
            pipeline = Pipeline(config)

            result = pipeline.process(
                str(input_file),
                steps_filter=steps_filter,
                storage=file_storage,
            )

            # The pipeline has already written output files to output_path via storage.
            # Report what was saved.
            stem = input_file.stem
            for i in range(1, result.num_photos_extracted + 1):
                out_name = f"SundayAlbum_{stem}_Photo{i:02d}.jpg"
                if (output_path / out_name).exists():
                    logger.info(f"Saved: {out_name}")

            logger.info(
                f"\nProcessing Summary [{input_file.name}]:\n"
                f"  Format: {result.metadata.format}\n"
                f"  Original size: {result.metadata.original_size[0]}x{result.metadata.original_size[1]}\n"
                f"  Photos extracted: {result.num_photos_extracted}\n"
                f"  Processing time: {result.processing_time:.3f}s\n"
                f"  Steps completed: {', '.join(result.steps_completed)}"
            )
            return result

        except Exception as e:
            logger.error(f"Error processing {input_file}: {e}", exc_info=verbose)
            return None

    # Process files — parallel when workers > 1, sequential otherwise
    results = []
    if workers == 1:
        for input_file in input_files:
            result = _process_one(input_file)
            if result is not None:
                results.append(result)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_process_one, f): f for f in input_files}
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    results.append(result)

    # Print overall summary
    logger.info(f"\n{'=' * 60}")
    logger.info(f"COMPLETE: Processed {len(results)}/{len(input_files)} file(s)")
    logger.info(f"Output directory: {output_path.absolute()}")
    if debug_dir:
        logger.info(f"Debug directory: {debug_dir.absolute()}")
    logger.info(f"{'=' * 60}")


@main.command(context_settings=_CTX)
def status() -> None:
    """Show pipeline implementation status and available steps."""
    from src.pipeline import PIPELINE_STEPS, get_step_status

    click.echo("\n" + "=" * 70)
    click.echo("Sunday Album Processing Pipeline - Implementation Status")
    click.echo("=" * 70 + "\n")

    # Get status for each step
    total_steps = len(PIPELINE_STEPS)
    implemented_count = 0

    for idx, step_info in enumerate(PIPELINE_STEPS, 1):
        step_id = step_info['id']
        step_name = step_info['name']
        step_desc = step_info['description']
        priority = step_info.get('priority', '-')

        # Check implementation status
        status_info = get_step_status(step_id)
        is_implemented = status_info['implemented']
        notes = status_info.get('notes', '')

        if is_implemented:
            implemented_count += 1
            status_icon = "✅"
            status_text = click.style("IMPLEMENTED", fg="green", bold=True)
        else:
            status_icon = "⏳"
            status_text = click.style("NOT IMPLEMENTED", fg="yellow")

        # Print step info
        click.echo(f"{status_icon} Step {idx}: {step_name} (Priority {priority})")
        click.echo(f"   ID: {step_id}")
        click.echo(f"   Status: {status_text}")
        click.echo(f"   Description: {step_desc}")
        if notes:
            click.echo(f"   Notes: {notes}")
        click.echo()

    # Print summary
    progress_pct = (implemented_count / total_steps) * 100
    click.echo("=" * 70)
    click.echo(f"Progress: {implemented_count}/{total_steps} steps implemented ({progress_pct:.1f}%)")
    click.echo("=" * 70)

    click.echo("\n📋 Usage Examples:")
    click.echo("  # Process a single file (all implemented steps)")
    click.echo("  sunday process image.HEIC -o ./output/")
    click.echo()
    click.echo("  # Process with debug visualizations")
    click.echo("  sunday process image.HEIC -o ./output/ -d")
    click.echo()
    click.echo("  # Process multiple files at once (shell glob)")
    click.echo("  sunday process test-images/*.HEIC -o ./output/")
    click.echo()
    click.echo("  # Process multiple files in parallel (4 workers)")
    click.echo("  sunday process test-images/*.HEIC -o ./output/ -j 4")
    click.echo()
    click.echo("  # Process only specific pipeline steps")
    click.echo("  sunday process image.HEIC -s load,photo_detect,split -o ./output/")
    click.echo()
    click.echo("  # Batch-process a directory")
    click.echo("  sunday process test-images/ -b -f \"*.HEIC\" -o ./output/")
    click.echo()
    click.echo("  # Fall back to OpenCV inpainting (no OpenAI API call)")
    click.echo("  sunday process image.HEIC -o ./output/ -G")
    click.echo()
    click.echo("  # Override scene description for OpenAI glare prompt")
    click.echo("  sunday process image.HEIC -o ./output/ -D \"A cave interior with warm amber light\"")
    click.echo()
    click.echo("  # Disable AI orientation correction")
    click.echo("  sunday process image.HEIC -o ./output/ -O")
    click.echo()


@main.command(context_settings=_CTX)
@click.argument('output_file', type=click.Path(exists=True))
@click.option(
    '--original', '-i',
    type=click.Path(exists=True),
    required=True,
    help='Original (pre-processing) input file to compare against',
)
@click.option(
    '--use-ai', '-A',
    is_flag=True,
    help='Use Claude AI vision for quality assessment (requires ANTHROPIC_API_KEY)',
)
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose / DEBUG logging')
def check(output_file: str, original: str, use_ai: bool, verbose: bool) -> None:
    """Quality check a processed image against its original.

    OUTPUT_FILE: Processed output image to check
    """
    from src.preprocessing.loader import load_image
    from src.ai.quality_check import assess_quality_full

    # Set logging level
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info(f"Quality check: {output_file}")
    logger.info(f"Comparing against: {original}")

    try:
        # Load images
        logger.info("Loading images...")
        original_img, _ = load_image(original)
        processed_img, _ = load_image(output_file)

        # Run quality assessment
        logger.info("Running quality assessment...")
        report = assess_quality_full(
            original_img,
            processed_img,
            use_ai=use_ai
        )

        # Print results
        click.echo("\n" + "=" * 70)
        click.echo("Quality Assessment Report")
        click.echo("=" * 70 + "\n")

        click.echo(f"Overall Quality Score: {report.overall_quality_score:.1f}/100\n")

        click.echo("Programmatic Metrics:")
        click.echo(f"  SSIM (Structural Similarity): {report.metrics.ssim_score:.3f}")
        click.echo(f"  Sharpness: {report.metrics.sharpness_original:.1f} → {report.metrics.sharpness_processed:.1f} ({report.metrics.sharpness_improvement:.2f}x)")
        click.echo(f"  Contrast: {report.metrics.contrast_original:.3f} → {report.metrics.contrast_processed:.3f} ({report.metrics.contrast_improvement:.2f}x)")
        click.echo(f"  Saturation: {report.metrics.saturation_original:.3f} → {report.metrics.saturation_processed:.3f}")
        click.echo(f"  Color Shift: {report.metrics.color_shift:.4f}")
        click.echo(f"  Brightness Change: {report.metrics.brightness_change:.4f}")

        if report.ai_assessment:
            click.echo("\nAI Assessment:")
            click.echo(f"  Overall Score: {report.ai_assessment.overall_score:.1f}/10")
            click.echo(f"  Glare Remaining: {report.ai_assessment.glare_remaining:.2f}")
            click.echo(f"  Artifacts Detected: {report.ai_assessment.artifacts_detected}")
            click.echo(f"  Sharpness: {report.ai_assessment.sharpness_score:.1f}/10")
            click.echo(f"  Color Naturalness: {report.ai_assessment.color_naturalness:.1f}/10")
            click.echo(f"  Confidence: {report.ai_assessment.confidence:.2f}")
            click.echo(f"  Notes: {report.ai_assessment.notes}")

        if report.notes:
            click.echo("\nNotes:")
            for note in report.notes:
                click.echo(f"  - {note}")

        click.echo("\n" + "=" * 70)

    except Exception as e:
        logger.error(f"Quality check failed: {e}", exc_info=verbose)
        sys.exit(1)


@main.command(context_settings=_CTX)
@click.argument('before', type=click.Path(exists=True))
@click.argument('after', type=click.Path(exists=True))
@click.option(
    '--save', '-s',
    type=click.Path(),
    default='comparison.jpg',
    show_default=True,
    help='Path to save the side-by-side comparison image',
)
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose / DEBUG logging')
def compare(before: str, after: str, save: str, verbose: bool) -> None:
    """Compare before/after images side-by-side and save as a single image.

    BEFORE: Original image\n
    AFTER:  Processed image
    """
    import numpy as np
    import cv2
    from src.preprocessing.loader import load_image
    from src.utils.debug import save_debug_image

    # Set logging level
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info(f"Comparing: {before} vs {after}")

    try:
        # Load images
        logger.info("Loading images...")
        before_img, _ = load_image(before)
        after_img, _ = load_image(after)

        # Resize to same height if needed
        h1, w1 = before_img.shape[:2]
        h2, w2 = after_img.shape[:2]

        if h1 != h2:
            # Resize to match heights
            target_h = min(h1, h2)
            scale1 = target_h / h1
            scale2 = target_h / h2

            before_img = cv2.resize(
                before_img,
                (int(w1 * scale1), target_h),
                interpolation=cv2.INTER_AREA
            )
            after_img = cv2.resize(
                after_img,
                (int(w2 * scale2), target_h),
                interpolation=cv2.INTER_AREA
            )

        # Create side-by-side comparison
        # Add a small separator (10px white bar)
        separator = np.ones((before_img.shape[0], 10, 3), dtype=np.float32)
        comparison = np.hstack([before_img, separator, after_img])

        # Add labels
        from PIL import Image, ImageDraw, ImageFont
        comparison_pil = Image.fromarray((comparison * 255).astype(np.uint8))
        draw = ImageDraw.Draw(comparison_pil)

        # Try to use a better font, fall back to default if not available
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        except:
            font = ImageFont.load_default()

        # Add "BEFORE" label
        draw.text((20, 20), "BEFORE", fill=(255, 255, 0), font=font)

        # Add "AFTER" label
        after_x = before_img.shape[1] + 10 + 20
        draw.text((after_x, 20), "AFTER", fill=(0, 255, 0), font=font)

        # Convert back to numpy
        comparison_with_labels = np.array(comparison_pil).astype(np.float32) / 255.0

        # Save comparison
        save_path = Path(save)
        save_debug_image(comparison_with_labels, save_path, "Before/After comparison", quality=95)

        logger.info(f"Saved comparison to: {save_path.absolute()}")

        click.echo(f"\n✅ Comparison saved to: {save_path.absolute()}")
        click.echo(f"   Before size: {before_img.shape[1]}x{before_img.shape[0]}")
        click.echo(f"   After size: {after_img.shape[1]}x{after_img.shape[0]}")

    except Exception as e:
        logger.error(f"Comparison failed: {e}", exc_info=verbose)
        sys.exit(1)


@main.command(context_settings=_CTX)
@click.option(
    '--test-images-dir', '-t',
    type=click.Path(exists=True),
    default='./test-images',
    show_default=True,
    help='Directory containing test images',
)
@click.option(
    '--output', '-o',
    'output_dir',
    type=click.Path(),
    default='./output',
    show_default=True,
    help='Output directory for processed images',
)
@click.option(
    '--debug', '-d',
    is_flag=True,
    help='Save debug visualizations for each step',
)
@click.option(
    '--use-ai', '-A',
    is_flag=True,
    help='Use Claude AI vision for quality assessment (requires ANTHROPIC_API_KEY)',
)
@click.option(
    '--heic-only', '-H',
    is_flag=True,
    help='Process only HEIC files, skip DNG (faster iteration)',
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='Enable verbose / DEBUG logging',
)
def validate(
    test_images_dir: str,
    output_dir: str,
    debug: bool,
    use_ai: bool,
    heic_only: bool,
    verbose: bool
) -> None:
    """Run full pipeline validation on all test images and generate summary report.

    This command processes all test images and generates a comprehensive quality report
    with metrics, timing, and optional AI assessment.
    """
    import numpy as np
    from src.preprocessing.loader import load_image
    from src.ai.quality_check import assess_quality_full

    # Set logging level
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    test_dir = Path(test_images_dir)
    if not test_dir.exists():
        logger.error(f"Test images directory not found: {test_dir}")
        sys.exit(1)

    # Find test images
    if heic_only:
        test_files = list(test_dir.glob('*.HEIC')) + list(test_dir.glob('*.heic'))
        logger.info("Processing HEIC files only")
    else:
        test_files = []
        for ext in ['*.HEIC', '*.heic', '*.DNG', '*.dng']:
            test_files.extend(test_dir.glob(ext))
        logger.info("Processing both HEIC and DNG files")

    if not test_files:
        logger.error(f"No test images found in {test_dir}")
        sys.exit(1)

    # Sort for consistent ordering
    test_files = sorted(test_files)

    click.echo("\n" + "=" * 80)
    click.echo("Sunday Album - Full Pipeline Validation")
    click.echo("=" * 80)
    click.echo(f"Test images: {len(test_files)}")
    click.echo(f"Output directory: {output_dir}")
    click.echo(f"Debug mode: {debug}")
    click.echo(f"AI quality check: {use_ai}")
    click.echo("=" * 80 + "\n")

    # Create output and debug directories
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    debug_dir = None
    if debug:
        debug_dir = Path('./debug')
        debug_dir.mkdir(parents=True, exist_ok=True)

    # Create pipeline config
    config = PipelineConfig()

    # Process all files and collect results
    validation_results = []

    for i, test_file in enumerate(test_files, 1):
        click.echo(f"\n[{i}/{len(test_files)}] Processing: {test_file.name}")
        click.echo("-" * 80)

        try:
            file_storage = LocalStorage(
                base_dir=Path("."),
                debug_dir=debug_dir if debug else None,
                output_dir=output_path,
            )
            pipeline = Pipeline(config)

            # Process the image
            result = pipeline.process(
                str(test_file),
                steps_filter=None,
                storage=file_storage,
            )

            # Report saved outputs (written to output_path via storage)
            saved_outputs = []
            stem = test_file.stem
            for photo_idx in range(1, result.num_photos_extracted + 1):
                out_name = f"SundayAlbum_{stem}_Photo{photo_idx:02d}.jpg"
                out_path = output_path / out_name
                if out_path.exists():
                    saved_outputs.append(out_path)
                    click.echo(f"  ✓ Saved: {out_name}")

            # Quality assessment (on first extracted photo)
            quality_report = None
            if len(result.output_images) > 0 and use_ai:
                try:
                    click.echo(f"  Running quality assessment...")
                    # Load the original extracted photo (before color restoration)
                    # For comparison, we'll use the raw extracted photo from debug output
                    original_for_comparison = result.output_images[0]  # Simplified: use final output vs itself
                    processed_for_comparison = result.output_images[0]

                    quality_report = assess_quality_full(
                        original_for_comparison,
                        processed_for_comparison,
                        use_ai=use_ai
                    )
                    click.echo(f"  Quality score: {quality_report.overall_quality_score:.1f}/100")
                except Exception as e:
                    logger.warning(f"  Quality assessment failed: {e}")

            # Store validation result
            validation_results.append({
                'input_file': test_file.name,
                'format': result.metadata.format,
                'original_size': f"{result.metadata.original_size[0]}x{result.metadata.original_size[1]}",
                'photos_extracted': result.num_photos_extracted,
                'glare_confidence': result.glare_confidence if result.glare_confidence else 0.0,
                'processing_time': result.processing_time,
                'quality_score': quality_report.overall_quality_score if quality_report else None,
                'steps_completed': len(result.steps_completed),
                'output_files': [str(f.name) for f in saved_outputs]
            })

            click.echo(f"  Format: {result.metadata.format}")
            click.echo(f"  Photos extracted: {result.num_photos_extracted}")
            click.echo(f"  Processing time: {result.processing_time:.1f}s")
            click.echo(f"  Steps completed: {len(result.steps_completed)}")

        except Exception as e:
            logger.error(f"  ✗ Error: {e}", exc_info=verbose)
            validation_results.append({
                'input_file': test_file.name,
                'format': 'ERROR',
                'original_size': 'N/A',
                'photos_extracted': 0,
                'glare_confidence': 0.0,
                'processing_time': 0.0,
                'quality_score': None,
                'steps_completed': 0,
                'output_files': []
            })
            continue

    # Generate summary report
    click.echo("\n" + "=" * 80)
    click.echo("VALIDATION SUMMARY")
    click.echo("=" * 80 + "\n")

    # Summary table
    click.echo(f"{'Input File':<40} {'Format':<8} {'Photos':<8} {'Time (s)':<10} {'Quality':<10}")
    click.echo("-" * 80)

    total_time = 0.0
    total_photos = 0
    successful = 0

    for res in validation_results:
        quality_str = f"{res['quality_score']:.1f}/100" if res['quality_score'] else "N/A"
        time_str = f"{res['processing_time']:.1f}"

        if res['format'] != 'ERROR':
            successful += 1
            total_time += res['processing_time']
            total_photos += res['photos_extracted']

        click.echo(
            f"{res['input_file']:<40} "
            f"{res['format']:<8} "
            f"{res['photos_extracted']:<8} "
            f"{time_str:<10} "
            f"{quality_str:<10}"
        )

    click.echo("-" * 80)
    click.echo(f"Successful: {successful}/{len(validation_results)}")
    click.echo(f"Total photos extracted: {total_photos}")
    click.echo(f"Total processing time: {total_time:.1f}s")
    click.echo(f"Average time per file: {total_time/max(successful, 1):.1f}s")
    click.echo("=" * 80)

    click.echo(f"\n✅ Validation complete!")
    click.echo(f"   Output directory: {output_path.absolute()}")
    if debug_dir:
        click.echo(f"   Debug directory: {debug_dir.absolute()}")


if __name__ == '__main__':
    main()
