from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

_scheduler = BackgroundScheduler()


def start_scheduler(job_func, minutes: int = 1):
    if _scheduler.get_job("etl_job"):
        _scheduler.remove_job("etl_job")

    _scheduler.add_job(
        job_func,
        trigger=IntervalTrigger(minutes=minutes),
        id="etl_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    if not _scheduler.running:
        _scheduler.start()
        print("scheduler started")


def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        print("scheduler stopped")
        
