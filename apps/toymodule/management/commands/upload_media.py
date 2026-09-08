"""Copy local MEDIA_ROOT files into the configured default storage.

Needed once, when moving to a deployment where uploads live in Supabase
Storage rather than on the local disk: the product rows travel via
dumpdata/loaddata, but the image files they name have to be put in the bucket
separately or every catalogue page renders broken images.

Run it locally with the Supabase variables set, so the source is this machine's
media/ directory and the destination is the bucket:

    DJANGO_DEBUG=True \\
    SUPABASE_S3_ENDPOINT=... SUPABASE_S3_REGION=... SUPABASE_S3_BUCKET=... \\
    SUPABASE_S3_ACCESS_KEY_ID=... SUPABASE_S3_SECRET_ACCESS_KEY=... \\
    python manage.py upload_media

Safe to re-run: files already in the bucket are skipped unless --overwrite.
"""

from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Upload every file under MEDIA_ROOT into the configured default storage."

    def add_arguments(self, parser):
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Replace files that already exist in the destination storage.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be uploaded without writing anything.",
        )

    def handle(self, *args, **options):
        if isinstance(default_storage._wrapped, FileSystemStorage) or isinstance(
            default_storage, FileSystemStorage
        ):
            raise CommandError(
                "The default storage is still the local filesystem, so this "
                "would copy media/ onto itself. Set SUPABASE_S3_ENDPOINT and "
                "the four SUPABASE_S3_* credentials before running this."
            )

        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.is_dir():
            raise CommandError(f"MEDIA_ROOT does not exist: {media_root}")

        overwrite = options["overwrite"]
        dry_run = options["dry_run"]
        uploaded = skipped = 0

        for path in sorted(p for p in media_root.rglob("*") if p.is_file()):
            # Storage keys are POSIX-style and relative to MEDIA_ROOT, matching
            # what ImageField stores in the database.
            name = path.relative_to(media_root).as_posix()

            if not overwrite and default_storage.exists(name):
                self.stdout.write(f"  skip    {name} (already present)")
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(f"  would upload {name}")
                uploaded += 1
                continue

            with path.open("rb") as fh:
                # save() would side-step overwrite by appending a suffix on
                # collision, so delete first when replacing deliberately.
                if overwrite and default_storage.exists(name):
                    default_storage.delete(name)
                saved_as = default_storage.save(name, File(fh))

            if saved_as != name:
                self.stdout.write(
                    self.style.WARNING(
                        f"  uploaded {name} as {saved_as} - a different file "
                        "already occupied that key; the product row still "
                        "points at the original name."
                    )
                )
            else:
                self.stdout.write(f"  upload  {name}")
            uploaded += 1

        verb = "would upload" if dry_run else "uploaded"
        self.stdout.write(
            self.style.SUCCESS(f"Done: {verb} {uploaded}, skipped {skipped}.")
        )
