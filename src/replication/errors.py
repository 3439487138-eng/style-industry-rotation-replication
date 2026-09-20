from __future__ import annotations


class ReplicationError(RuntimeError):
    label = "ERROR"
    exit_code = 1


class ConfigurationError(ReplicationError):
    label = "CONFIGURATION_ERROR"
    exit_code = 2


class ReplicationUnavailable(ReplicationError):
    label = "UNAVAILABLE"
    exit_code = 3


class AdapterError(ReplicationError):
    label = "ADAPTER_ERROR"
    exit_code = 4


class ReportError(ReplicationError):
    label = "REPORT_ERROR"
    exit_code = 5
