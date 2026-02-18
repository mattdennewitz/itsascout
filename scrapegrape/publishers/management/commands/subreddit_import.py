"""Import article URLs from a Reddit subreddit's JSON feed into the analysis pipeline."""

import httpx
from django.core.management.base import BaseCommand

from publishers.models import Publisher, ResolutionJob
from publishers.pipeline import run_pipeline
from publishers.url_sanitizer import extract_domain, sanitize_url

REDDIT_USER_AGENT = "itsascout:subreddit_import/0.1 (by /u/itsascout)"


class Command(BaseCommand):
    help = "Import URLs from a subreddit and queue them for the analysis pipeline."

    def add_arguments(self, parser):
        parser.add_argument("subreddit", type=str, help="Subreddit name (e.g. politics)")

    def handle(self, *args, **options):
        subreddit = options["subreddit"]
        url = f"https://www.reddit.com/r/{subreddit}.json"

        self.stdout.write(f"Fetching {url} ...")
        resp = httpx.get(url, headers={"User-Agent": REDDIT_USER_AGENT}, timeout=15)
        resp.raise_for_status()

        children = resp.json().get("data", {}).get("children", [])
        self.stdout.write(f"Found {len(children)} posts")

        queued = 0
        skipped = 0

        for child in children:
            article_url = child.get("data", {}).get("url_overridden_by_dest")
            if not article_url:
                continue

            # Skip reddit self-posts and other reddit links
            if "reddit.com" in article_url or "redd.it" in article_url:
                continue

            try:
                canonical_url = sanitize_url(article_url)
                domain = extract_domain(article_url)
            except (ValueError, TypeError):
                self.stderr.write(f"  SKIP (invalid URL): {article_url}")
                skipped += 1
                continue

            if not domain:
                self.stderr.write(f"  SKIP (no domain): {article_url}")
                skipped += 1
                continue

            # Skip if a non-failed job already exists for this canonical URL
            existing = ResolutionJob.objects.filter(
                canonical_url=canonical_url,
                status__in=("pending", "running", "completed"),
            ).exists()
            if existing:
                self.stdout.write(f"  SKIP (exists): {canonical_url}")
                skipped += 1
                continue

            # Get or create publisher
            publisher_url = f"https://{domain}"
            publisher, _ = Publisher.objects.get_or_create(
                domain=domain, defaults={"name": domain, "url": publisher_url}
            )

            # Create job and queue pipeline
            job = ResolutionJob.objects.create(
                submitted_url=article_url,
                canonical_url=canonical_url,
                publisher=publisher,
            )
            run_pipeline.delay(str(job.id))
            self.stdout.write(f"  QUEUED: {canonical_url}")
            queued += 1

        self.stdout.write(self.style.SUCCESS(f"\nDone: {queued} queued, {skipped} skipped"))
