import json
import os
import tempfile
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional

from loguru import logger
from tqdm import tqdm
from sh import xsv, wafw00f, ErrorReturnCode


def load_urls_from_csv(csv_file: str = "sites.csv", limit: int = 5) -> List[str]:
    """Load URLs from CSV file using xsv."""
    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"CSV file {csv_file} not found")

    lines = xsv("select", "-n", str(limit), csv_file)
    urls = lines.splitlines()
    return urls


def scan_url_with_wafw00f(url: str) -> Optional[Dict[str, Any]]:
    """Scan a single URL with wafw00f and return the result."""
    try:
        with tempfile.NamedTemporaryFile(delete_on_close=False) as tf:
            tf.close()

            wafw00f("-f", "json", "-o", tf.name, url)

            if not os.path.exists(tf.name):
                logger.error(f"wafw00f output file not created for {url}")
                return None

            with open(tf.name, "r") as f:
                result = json.load(f)

            os.remove(tf.name)

            bits = urlparse(url)
            return {
                "base_url": f"{bits.scheme}://{bits.netloc}",
                "report": result,
            }
    except ErrorReturnCode as e:
        logger.error(f"wafw00f command failed for {url}: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON output for {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error scanning {url}: {e}")
        return None


def save_reports_to_json(
    reports: List[Dict[str, Any]], output_file: str = "reports.json"
) -> None:
    """Save reports to JSON file."""
    try:
        with open(output_file, "w") as f:
            json.dump(reports, f, indent=2)
        logger.info(f"Saved {len(reports)} reports to {output_file}")
    except Exception as e:
        logger.error(f"Error saving reports to JSON: {e}")
        raise


def main() -> None:
    """Main function to orchestrate the WAF checking workflow."""
    try:
        urls = load_urls_from_csv()
        reports = []

        with tqdm(urls) as pbar:
            for url in urls:
                pbar.set_description(url[:50])
                if url:
                    report = scan_url_with_wafw00f(url)
                    if report:
                        reports.append(report)
                pbar.update(1)

        save_reports_to_json(reports)
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        raise


if __name__ == "__main__":
    main()
