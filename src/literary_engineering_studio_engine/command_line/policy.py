"""Stable command-surface policy for the embedded Engine CLI."""

FORMAL_HELP_COMMANDS = {
    "formal-help", "help-all", "protocol", "workflow-dashboard", "workflow-state",
    "task-next", "task-open", "task-submit", "task-complete", "workflow-advance",
    "workflow-events", "workflow-validate", "agent-task-status", "route-audit", "canon-backlog",
}

FORMAL_HELP_METAVAR = (
    "{formal-help,workflow-dashboard,task-next,task-open,"
    "task-submit,task-complete,route-audit,help-all}"
)

STUDIO_DISABLED_COMMANDS = {
    "agent-run", "agent-repair", "config-init", "config-set-profile", "config-show",
    "dify-dsl", "director-chat", "run-langgraph", "run-workflow", "serve-api",
}
