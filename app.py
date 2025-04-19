import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# Define multiple Prometheus data sources (Prometheus and VictoriaMetrics)
PROMETHEUS_SOURCES = {
    "prometheus-tabriz": {
        "url": "http://ipaddress:10909/",  # Prometheus API endpoint
        "type": "prometheus"
    },
    "VictoriaMetrics": {
        "url": "http://ipaddres:port",  # VictoriaMetrics API endpoint
        "type": "victoria"
    },
    # Add more sources as needed
}


HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Prometheus Query UI</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .label-box { font-size: 0.85rem; color: #555; }
        .label-badge {
            display: inline-block;
            background-color: #f0f0f0;
            border-radius: 4px;
            padding: 2px 6px;
            margin: 2px;
            font-size: 0.8rem;
        }
        code {
            font-size: 0.9rem;
            background-color: #eee;
            padding: 2px 4px;
            border-radius: 4px;
        }
        .logo {
            max-height: 60px;
        }
    </style>
</head>
<body class="bg-light py-5">
<div class="container">
    <div class="text-center mb-4">
        <img src="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQYqry39qPgaCHxiJe4hZgwbt2hZg3_tb0YNA&s" alt="Mon Logo" class="logo">
    </div>
    <h2 class="mb-4 text-center">📊 Monitoring Query Dashboard</h2>

    <form method="POST" action="/query-ui" class="mb-4">
        <div class="form-floating mb-3">
            <input type="text" class="form-control" id="queryInput" name="query" placeholder="Type PromQL query here..." value="{{ default_query }}">
            <label for="queryInput">Query</label>
        </div>
        <div class="form-floating mb-3">
            <select class="form-select" id="datasourceSelect" name="datasource" required>
                {% for source_name, source_info in prometheus_sources.items() %}
                <option value="{{ source_info.url }}">{{ source_name }}</option>
                {% endfor %}
            </select>
            <label for="datasourceSelect">Data Source</label>
        </div>
        <button type="submit" class="btn btn-primary">Run Query</button>
    </form>

    {% if error %}
    <div class="alert alert-danger" role="alert">{{ error }}</div>
    {% endif %}

    {% if result %}
    <div class="card shadow">
        <div class="card-header bg-dark text-white">
            <strong>Query Result</strong> <span class="float-end"><code>{{ query }}</code></span>
        </div>
        <div class="card-body p-0">
            <table class="table table-bordered table-hover mb-0">
                <thead class="table-light">
                    <tr>
                        <th>Labels</th>
                        <th>Instance</th>
                        <th>Value</th>
                        <th>Timestamp</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in result %}
                    <tr>
                        <td>
                            {% for label in row.labels %}
                            <span class="label-badge">{{ label }}</span>
                            {% endfor %}
                        </td>
                        <td>{{ row.instance }}</td>
                        <td>{{ row.value }}</td>
                        <td>{{ row.timestamp }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    {% elif no_data %}
    <div class="alert alert-warning" role="alert">No data found for this query.</div>
    {% endif %}
</div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE, result=None, error=None, default_query="", query="", prometheus_sources=PROMETHEUS_SOURCES)

@app.route('/query-ui', methods=['POST'])
def query_ui():
    promql_query = request.form.get('query', '').strip()
    datasource_url = request.form.get('datasource', '').strip()

    if not promql_query:
        return render_template_string(HTML_PAGE, result=None, error="Missing query.", default_query="", query="", prometheus_sources=PROMETHEUS_SOURCES)

    if not datasource_url or datasource_url not in [source['url'] for source in PROMETHEUS_SOURCES.values()]:
        return render_template_string(HTML_PAGE, result=None, error="Invalid data source.", default_query=promql_query, query=promql_query, prometheus_sources=PROMETHEUS_SOURCES)

    # Get the type of data source
    data_source_info = next((source for source in PROMETHEUS_SOURCES.values() if source['url'] == datasource_url), None)
    if data_source_info is None:
        return render_template_string(HTML_PAGE, result=None, error="Invalid data source.", default_query=promql_query, query=promql_query, prometheus_sources=PROMETHEUS_SOURCES)

    data_source_type = data_source_info['type']
    try:
        # Handle Prometheus vs VictoriaMetrics query URLs
        if data_source_type == 'victoria':
            url = f'{datasource_url}/select/0/prometheus/api/v1/query'
        else:
            url = f'{datasource_url}/api/v1/query'

        r = requests.get(url, params={'query': promql_query}, verify=False)

        # Check if the status code is 200
        if r.status_code != 200:
            return render_template_string(HTML_PAGE, result=None, error=f"Error: {r.status_code} - {r.text}", default_query=promql_query, query=promql_query, prometheus_sources=PROMETHEUS_SOURCES)

        data = r.json()

        if data['status'] != 'success':
            return render_template_string(HTML_PAGE, result=None, error="Prometheus query failed.", default_query=promql_query, query=promql_query, prometheus_sources=PROMETHEUS_SOURCES)

        # If no data returned, show "No Data Found"
        if not data['data']['result']:
            return render_template_string(HTML_PAGE, result=None, error="No Data Found", default_query=promql_query, query=promql_query, prometheus_sources=PROMETHEUS_SOURCES)

        results = []
        for item in data['data']['result']:
            metric = item.get('metric', {})
            metric_name = metric.get('__name__') or 'Expression Result'
            labels = [f'{k}="{v}"' for k, v in metric.items() if k != '__name__']
            instance = metric.get('instance', 'N/A')
            value = item['value'][1]
            timestamp = item['value'][0]

            results.append({
                'metric': metric_name,
                'labels': labels,
                'instance': instance,
                'value': value,
                'timestamp': timestamp
            })

        return render_template_string(HTML_PAGE, result=results, error=None, default_query=promql_query, query=promql_query, prometheus_sources=PROMETHEUS_SOURCES)

    except requests.exceptions.RequestException as e:
        return render_template_string(HTML_PAGE, result=None, error=str(e), default_query=promql_query, query=promql_query, prometheus_sources=PROMETHEUS_SOURCES)
    
# REST API still available
@app.route('/query-metric', methods=['POST'])
def query_metric():
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({'error': 'Malformed JSON in request body'}), 400

    promql_query = data.get('query')
    datasource_url = data.get('datasource')
    if not promql_query or not datasource_url:
        return jsonify({'error': 'Missing "query" or "datasource" in request body'}), 400

    if datasource_url not in [source['url'] for source in PROMETHEUS_SOURCES.values()]:
        return jsonify({'error': 'Invalid data source'}), 400

    # Get the type of data source
    data_source_info = next((source for source in PROMETHEUS_SOURCES.values() if source['url'] == datasource_url), None)
    if data_source_info is None:
        return jsonify({'error': 'Invalid data source'}), 400

    data_source_type = data_source_info['type']

    try:
        # Handle Prometheus vs VictoriaMetrics query URLs
        if data_source_type == 'victoria':
            url = f'{datasource_url}/select/0/prometheus/api/v1/query'
        else:
            url = f'{datasource_url}/api/v1/query'

        response = requests.get(url, params={'query': promql_query}, verify=False)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005, debug=True)
