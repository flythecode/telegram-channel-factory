from urllib.request import urlopen

API_HEALTH_URL = 'http://127.0.0.1:8000/health'



def main() -> int:
    try:
        response = urlopen(API_HEALTH_URL, timeout=5)
        if response.status != 200:
            print(f'api unhealthy: status={response.status}')
            return 1
        print('api healthy')
        return 0
    except Exception as exc:  # pragma: no cover - network dependent
        print(f'api unhealthy: error={exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
