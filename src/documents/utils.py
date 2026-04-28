import logging
import re
import shutil
from collections import Counter
from os import utime
from pathlib import Path
from subprocess import CompletedProcess
from subprocess import run

from django.conf import settings
from PIL import Image

if getattr(settings, 'NLTK_ENABLED', False):
    try:
        from nltk.corpus import stopwords

        NLTK_AVAILABLE = True
    except ImportError:
        NLTK_AVAILABLE = False
else:
    NLTK_AVAILABLE = False


def _coerce_to_path(
    source: Path | str,
    dest: Path | str,
) -> tuple[Path, Path]:
    return Path(source).resolve(), Path(dest).resolve()


def copy_basic_file_stats(source: Path | str, dest: Path | str) -> None:
    """
    Copies only the m_time and a_time attributes from source to destination.
    Both are expected to exist.

    The extended attribute copy does weird things with SELinux and files
    copied from temporary directories and copystat doesn't allow disabling
    these copies.

    If there is a PermissionError, skip copying file stats.
    """
    source, dest = _coerce_to_path(source, dest)
    src_stat = source.stat()

    try:
        utime(dest, ns=(src_stat.st_atime_ns, src_stat.st_mtime_ns))
    except PermissionError:
        pass


def copy_file_with_basic_stats(
    source: Path | str,
    dest: Path | str,
) -> None:
    """
    A sort of simpler copy2 that doesn't copy extended file attributes,
    only the access time and modified times from source to dest.

    The extended attribute copy does weird things with SELinux and files
    copied from temporary directories.

    If there is a PermissionError (e.g., on ZFS with acltype=nfsv4)
    fall back to copyfile (data only).
    """
    source, dest = _coerce_to_path(source, dest)

    try:
        shutil.copy(source, dest)
    except PermissionError:
        shutil.copyfile(source, dest)

    copy_basic_file_stats(source, dest)


def maybe_override_pixel_limit() -> None:
    """
    Maybe overrides the PIL limit on pixel count, if configured to allow it
    """
    limit: float | int | None = settings.MAX_IMAGE_PIXELS
    if limit is not None and limit >= 0:
        pixel_count = limit
        if pixel_count == 0:
            pixel_count = None
        Image.MAX_IMAGE_PIXELS = pixel_count


def run_subprocess(
    arguments: list[str],
    env: dict[str, str] | None = None,
    logger: logging.Logger | None = None,
    *,
    check_exit_code: bool = True,
    log_stdout: bool = True,
    log_stderr: bool = True,
) -> CompletedProcess:
    """
    Runs a subprocess and logs its output, checking return code if requested
    """

    proc_name = arguments[0]

    completed_proc = run(args=arguments, env=env, capture_output=True, check=False)

    if logger:
        logger.info(f"{proc_name} exited {completed_proc.returncode}")

    if log_stdout and logger and completed_proc.stdout:
        stdout_str = (
            completed_proc.stdout.decode("utf8", errors="ignore")
            .strip()
            .split(
                "\n",
            )
        )
        logger.info(f"{proc_name} stdout:")
        for line in stdout_str:
            logger.info(line)

    if log_stderr and logger and completed_proc.stderr:
        stderr_str = (
            completed_proc.stderr.decode("utf8", errors="ignore")
            .strip()
            .split(
                "\n",
            )
        )
        logger.info(f"{proc_name} stderr:")
        for line in stderr_str:
            logger.warning(line)

    # Last, if requested, after logging outputs
    if check_exit_code:
        completed_proc.check_returncode()

    return completed_proc


def get_boolean(boolstr: str) -> bool:
    """
    Return a boolean value from a string representation.
    """
    return bool(boolstr.lower() in ("yes", "y", "1", "t", "true"))


def suggest_title_from_content(content: str, lang: str = "english", document=None) -> str | None:
    """
    Suggests a title from the document content by extracting the most
    frequent keywords.
    """
    if not content:
        return None

    # Take the first part of the content to speed up processing and get more relevant words
    words = re.findall(r"\b\w{4,}\b", content.lower())[:1000]

    if NLTK_AVAILABLE:
        try:
            # TODO: This should respect PAPERLESS_OCR_LANGUAGE
            stop_words = set(stopwords.words(lang))
            words = [w for w in words if w not in stop_words and not w.isdigit()]
        except Exception:
            # Fallback if stopwords for the language are not available
            pass

    if not words:
        return None

    # Get the most common word
    most_common = [word for word, count in Counter(words).most_common(1)]

    if not most_common:
        return None

    most_significant_word = most_common[0].capitalize()
    title_parts = [most_significant_word]

    if document:
        field_value = None
        if hasattr(document, "field_values"):
            for fv in document.field_values.all():
                if fv.value:
                    field_value = fv.value
                    # Ne oprim dacă găsim un field specific (ex: 'nume')
                    if "nume" in fv.template_field.name.lower():
                        break

        if field_value:
            # Eliminăm spațiile pentru formatul cerut
            title_parts.append(field_value.replace(" ", ""))

        if document.id:
            title_parts.append(str(document.id))

    return "_".join(title_parts)
