import argparse
import asyncio
import json
import logging

from sqlalchemy import text

from app.database.session import SessionLocal
from app.services.scraping import export_jobs, scrape


def parser():
    p = argparse.ArgumentParser(prog="techjobs")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("scrape")
    s.add_argument(
        "--source",
        choices=["greenhouse", "lever", "ashby", "adzuna", "usajobs", "jobicy", "jooble"],
    )
    s.add_argument("--country")
    s.add_argument("--region")
    s.add_argument("--company")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--max-pages", type=int)
    s.add_argument("--max-jobs", type=int)
    sub.add_parser("jobs")
    e = sub.add_parser("export")
    e.add_argument("--format", choices=["csv", "json", "jsonl"], default="csv")
    e.add_argument("--output")
    sub.add_parser("health")
    return p


async def main(args):
    if args.command == "scrape":
        print(
            json.dumps(
                await scrape(
                    args.source,
                    args.country,
                    args.region,
                    args.company,
                    args.dry_run,
                    args.max_pages,
                    args.max_jobs,
                ),
                indent=2,
            )
        )
    elif args.command == "export":
        print(await export_jobs(args.format, args.output))
    elif args.command == "jobs":
        async with SessionLocal() as session:
            print(await session.scalar(text("SELECT count(*) FROM jobs")) or 0)
    elif args.command == "health":
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        print("database=ok")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main(parser().parse_args()))
