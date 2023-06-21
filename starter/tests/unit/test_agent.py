import pytest

from starter.app.agent import AgentSpecTemplate, AgentSpecValidationError


@pytest.fixture(scope="session")
def template():
    return AgentSpecTemplate("agent.yaml")


def test_validate_ok(template: AgentSpecTemplate):
    agent_spec = template.copy()
    agent_spec.set_label("fuzzer_id", "1111")
    agent_spec.set_label("fuzzer_rev", "2222")
    agent_spec.set_label("agent_mode", "first-run")
    agent_spec.set_command("echo 'lalala'")
    agent_spec.as_dict()


def test_validate_fail(template: AgentSpecTemplate):
    agent_spec = template.copy()
    agent_spec.set_image_name(None)
    with pytest.raises(AgentSpecValidationError):
        agent_spec.as_dict()


def test_agent_spec(template: AgentSpecTemplate):

    agent_spec = template.copy()
    agent_spec.set_grace_period(60)
    agent_spec.set_deadline_seconds(300)
    agent_spec.set_label("fuzzer_id", "1111")
    agent_spec.set_label("fuzzer_rev", "2222")
    agent_spec.set_label("agent_mode", "first-run")
    agent_spec.set_container_name("myfuzzer")
    agent_spec.set_image_name("busybox")
    agent_spec.set_rs_requests("100m", "1000M")
    agent_spec.set_rs_limits("200m", "2000M")
    agent_spec.set_env("MY_ENV1", "val1")
    agent_spec.set_env("MY_ENV2", "val2")
    agent_spec.set_command("echo this")
    body = agent_spec.as_dict()

    expected_body = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "generateName": "fuzzer-",
            "labels": {
                "fuzzer_id": "1111",
                "fuzzer_rev": "2222",
                "agent_mode": "first-run",
            },
        },
        "spec": {
            "activeDeadlineSeconds": 300,
            "terminationGracePeriodSeconds": 60,
            "restartPolicy": "Never",
            "containers": [
                {
                    "name": "myfuzzer",
                    "image": "busybox",
                    "command": ["sh", "-c", "echo this"],
                    "env": [
                        {"name": "MY_ENV1", "value": "val1"},
                        {"name": "MY_ENV2", "value": "val2"},
                    ],
                    "resources": {
                        "requests": {
                            "cpu": "100m",
                            "memory": "1000M",
                        },
                        "limits": {
                            "cpu": "200m",
                            "memory": "2000M",
                        },
                    },
                    "volumeMounts": [
                        {"name": "tmpfs", "mountPath": "/mnt/tmpfs"},
                        {"name": "disk", "mountPath": "/mnt/disk"},
                    ],
                }
            ],
            "volumes": [
                {
                    "name": "tmpfs",
                    "emptyDir": {
                        "medium": "Memory",
                        "sizeLimit": "64M",
                    },
                },
                {
                    "name": "disk",
                    "emptyDir": {
                        "sizeLimit": "64M",
                    },
                },
            ],
        },
    }

    assert body == expected_body
