"""Run the local backend: python -m dungeon"""
import uvicorn

from dungeon.identity import DEFAULT_PORT


def main():
    uvicorn.run('dungeon.main:create_app', factory=True, host='127.0.0.1', port=DEFAULT_PORT)


if __name__ == '__main__':
    main()
