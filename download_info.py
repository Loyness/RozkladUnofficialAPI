import argparse
import json
import requests
from bs4 import BeautifulSoup


def parse_table(table):
    rows = []
    for tr in table.find_all('tr'):
        cells = [cell.get_text(strip=True) for cell in tr.find_all(['th', 'td'])]
        if cells:
            rows.append(cells)
    return rows


def parse_pipes(text):
    lines = [l for l in text.splitlines() if '|' in l]
    rows = []
    for line in lines:
        parts = [p.strip() for p in line.split('|')]
        if any(p != '' for p in parts):
            rows.append(parts)
    return rows


def parse(html):
    soup = BeautifulSoup(html, 'html.parser')
    def extract_js_json_var(text, varname='data'):
        marker = f"var {varname}"
        i = text.find(marker)
        if i == -1:
            return None
        j = text.find('{', i)
        if j == -1:
            return None
        depth = 0
        in_str = False
        esc = False
        end = None
        for k in range(j, len(text)):
            ch = text[k]
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == in_str:
                    in_str = False
            else:
                if ch == '"' or ch == "'":
                    in_str = ch
                elif ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        end = k
                        break
        if end is None:
            return None
        js_text = text[j:end+1]
        try:
            return json.loads(js_text)
        except Exception:
            return None

    tables = soup.find_all('table')
    js_data = extract_js_json_var(html)
    if js_data is not None:
        return js_data
    if tables:
        table = max(tables, key=lambda t: len(t.find_all('tr')))
        return parse_table(table)
    pre = soup.find('pre')
    if pre:
        return parse_pipes(pre.get_text())
    text = soup.get_text('\n')
    rows = parse_pipes(text)
    return rows


def fetch(url):
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    return resp.text


def main():
    parser = argparse.ArgumentParser(description='Fetch and parse Rozklad information')
    parser.add_argument('url', nargs='?')
    parser.add_argument('--json', '-j', action='store_true', help='output JSON')
    parser.add_argument('--out', '-o', help='write output to file (JSON)')
    args = parser.parse_args()

    html = fetch(args.url)
    rows = parse(html)

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as fh:
            fh.write(json.dumps(rows, ensure_ascii=False, indent=2))
        print(f'Wrote output to {args.out}')
        return

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        if isinstance(rows, dict):
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            for r in rows:
                print(' | '.join(r))


if __name__ == '__main__':
    main()
