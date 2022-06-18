# Very simple web endpoints (urls) monitoring tool

Simple web monitoring which checks web endpoints for expecting response code/body and exports Prometheus metrics as result of its work.

0 - FAILED, 1 - OK
```
web_health_check{name="site1",url="https://site1.com/health_check"} 1.0
web_health_check{name="site2",url="https://site2.com/health_check"} 0.0
```

To get alerts [Alerting rules in Prometheus](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/) and [Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/) need to be configured.

List of urls to check are specified in [yaml config file](src/conf/config.yml).

See [similar tool](https://github.com/alexk2000/web-health-check-go) built with Go which, instead of exporting metrics, sends alerts to Slack.