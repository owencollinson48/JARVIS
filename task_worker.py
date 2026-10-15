"""Run one due check (Task Scheduler) or a local worker loop; never auto-enable paid services."""
import argparse
import time
from jarvis import create_app
from jarvis.communications import worker

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');args=parser.parse_args()
    app=create_app()
    while True:
        with app.app_context():worker()
        if args.once:break
        time.sleep(60)
