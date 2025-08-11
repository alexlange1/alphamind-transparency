# Validator examples

Aggregate and publish:

```bash
export AM_OUT_DIR=$(pwd)/subnet/out
export AM_API_TOKEN=dev
mkdir -p "$AM_OUT_DIR"

curl -s -X POST \
  -H "Authorization: Bearer ${AM_API_TOKEN}" \
  -H "content-type: application/json" \
  -d in_dir:'' \
  http://127.0.0.1:8000/aggregate | jq .

curl -s "http://127.0.0.1:8000/weightset-publish?in_dir=$AM_OUT_DIR" | jq .
```
