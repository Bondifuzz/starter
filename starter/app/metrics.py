from prometheus_client.metrics import Counter, Gauge

failed_pods_evicted_desc = "Count of pods which exhausted all available disk space"
failed_pods_evicted = Counter("failed_pods_evicted", failed_pods_evicted_desc)

failed_pods_oom_killed_desc = "Count of pods which exhausted all available RAM"
failed_pods_oom_killed = Counter("failed_pods_oom_killed", failed_pods_oom_killed_desc)

failed_pods_timeout_desc = "Count of pods which exceeded their run time"
failed_pods_timeout = Counter("failed_pods_deadline_exceeded", failed_pods_timeout_desc)

failed_pods_other_desc = "Count of pods which failed with unknown reasons"
failed_pods_other = Counter("failed_pods_other", failed_pods_other_desc)

pending_pods_desc = "Count of pods which are in pending state now"
pending_pods = Gauge("pending_pods", pending_pods_desc)

running_pods_desc = "Count of pods which are in running state now. Must be > 0"
running_pods = Gauge("running_pods", running_pods_desc)

succeeded_pods_desc = "Count of pods which are in completed state now. Must be 0"
succeeded_pods = Gauge("succeeded_pods", succeeded_pods_desc)

failed_pods_desc = "Count of pods which are in failed state now. Must be 0"
failed_pods = Gauge("failed_pods", failed_pods_desc)

unknown_pods_desc = "Count of pods which are in unknown state now. Must be 0"
unknown_pods = Gauge("unknown_pods", unknown_pods_desc)

k8s_listener_errors_desc = "Count of errors occurred during k8s events monitoring"
k8s_listener_errors = Counter("k8s_listener_unhandled_errors", k8s_listener_errors_desc)

pod_event_errors_desc = "Count of errors occurred during fuzzer pods events monitoring"
pod_event_errors = Counter("pod_event_loop_unhandled_errors", pod_event_errors_desc)
