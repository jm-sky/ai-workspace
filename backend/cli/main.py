"""Main CLI application.

This module configures the main Typer application and registers all command groups.
"""

import sys
from typing import Any

import questionary
import typer
from rich.console import Console
from rich.panel import Panel

from app.core.app_factory import init_sentry

# Initialize Typer app
app = typer.Typer(
    name="cli",
    help="Management CLI for FastAPI project - Django-inspired commands",
    add_completion=True,
    no_args_is_help=False,  # We handle no-args case ourselves for interactive mode
)

# Initialize Rich console (shared across commands)
console = Console()

# Command groups and their commands mapping
COMMAND_GROUPS = {
    "db": {
        "name": "Database Management",
        "commands": {
            "init": "Initialize database",
            "init-test": "Initialize test database (PostgreSQL)",
            "migrate": "Run pending migrations",
            "migrate-status": "Show migration status",
            "migrate-graceful": "Run migrations gracefully (ignore errors)",
            "migrate-unmark": "Unmark a migration (allows re-running)",
            "seed": "Seed database with initial data",
            "seed-remove": "Remove seeded data",
        },
    },
    "users": {
        "name": "User Management",
        "commands": {
            "create": "Create a new user",
            "list": "List all users",
            "delete": "Delete a user",
            "change-password": "Change a user's password",
            "verify-email": "Show or confirm email verification",
            "set-role": "Set user role (user, premium, admin, owner)",
            "toggle-admin": "Toggle admin status for a user",
            "toggle-owner": "Toggle owner status for a user",
        },
    },
    "tenants": {
        "name": "Tenant Management",
        "commands": {
            "create": "Create a new tenant",
            "assign": "Assign user to tenant",
            "list": "List all tenants",
        },
    },
    "test": {
        "name": "Testing & Debugging",
        "commands": {
            "sentry": "Test Sentry error reporting",
            "storage": "Test storage adapter",
            "email": "Test email sending",
            "ai": "Test AI module (OpenRouter)",
        },
    },
    "agent": {
        "name": "Agent & Chat",
        "commands": {
            "purge-orphans": "Delete unbound chat attachments older than TTL",
        },
    },
    "rag": {
        "name": "Document RAG",
        "commands": {
            "reembed": "Re-embed document_chunks behind the current AI_EMBEDDING_VERSION",
        },
    },
    "billing": {
        "name": "Billing & Subscriptions",
        "commands": {
            "change-plan": "Change a user's subscription plan (free, pro, pro_plus)",
        },
    },
}

# Commands that require arguments (command_path -> list of argument prompts)
# Each argument can be:
# - "type": "select" (for dropdown with choices) or "text" (for text input)
# - "arg_type": "positional" (typer.Argument) or "option" (typer.Option with flag)
# - "flag": flag name for options (e.g., "--owner-email")
COMMAND_ARGUMENTS = {
    "db.seed": [
        {
            "name": "seeder",
            "prompt": "Select seeder (use ↑↓ arrow keys, Enter to confirm):",
            "type": "select",
            "choices": ["catalogue"],
            "arg_type": "positional",
        },
    ],
    "db.seed-remove": [
        {
            "name": "seeder",
            "prompt": "Select seeder to remove (use ↑↓ arrow keys, Enter to confirm):",
            "type": "select",
            "choices": ["catalogue"],
            "arg_type": "positional",
        },
    ],
    "db.migrate-unmark": [
        {
            "name": "version",
            "prompt": "Enter migration version (e.g., '020'):",
            "type": "text",
            "arg_type": "positional",
        },
    ],
    "tenants.create": [
        {
            "name": "name",
            "prompt": "Enter tenant name:",
            "type": "text",
            "arg_type": "positional",
        },
        {
            "name": "email",
            "prompt": "Enter owner email:",
            "type": "text",
            "arg_type": "option",
            "flag": "--owner-email",
        },
    ],
    "tenants.assign": [
        {
            "name": "tenant_id",
            "prompt": "Enter tenant ID:",
            "type": "text",
            "arg_type": "positional",
        },
        {
            "name": "email",
            "prompt": "Enter user email:",
            "type": "text",
            "arg_type": "positional",
        },
    ],
    "test.email": [
        {
            "name": "to",
            "prompt": "Enter recipient email address:",
            "type": "text",
            "arg_type": "positional",
        },
    ],
}


def prompt_for_arguments(command_path: str) -> list[str]:
    """Prompt for required arguments for a command.

    Args:
        command_path: Full command path (e.g., "db.seed")

    Returns:
        List of argument/option values to append to sys.argv
        Positional arguments come first, then options with flags
    """
    if command_path not in COMMAND_ARGUMENTS:
        return []

    positional_args: list[str] = []
    option_args: list[str] = []
    arg_configs: list[dict[str, Any]] = COMMAND_ARGUMENTS[command_path]  # type: ignore[assignment]

    for arg_config in arg_configs:
        arg_name: str = str(arg_config["name"])
        arg_prompt: str = str(arg_config["prompt"])
        arg_type: str = str(arg_config.get("type", "text"))
        arg_arg_type: str = str(arg_config.get("arg_type", "positional"))

        if arg_type == "select":
            choices: list[str] = arg_config.get("choices", [])
            if not choices or not isinstance(choices, list):
                return []
            choice_objects = [questionary.Choice(title=str(choice), value=str(choice)) for choice in choices]
            value: str | None = questionary.select(
                arg_prompt,
                choices=choice_objects,
                use_arrow_keys=True,
                use_jk_keys=False,
                style=questionary.Style(
                    [
                        ("qmark", "fg:#673ab7 bold"),
                        ("question", "bold"),
                        ("answer", "fg:#f44336 bold"),
                        ("pointer", "fg:#673ab7 bold"),
                        ("highlighted", "fg:#673ab7 bold"),
                        ("selected", "fg:#cc5454"),
                        ("separator", "fg:#cc5454"),
                        ("instruction", ""),
                        ("text", ""),
                        ("disabled", "fg:#858585 italic"),
                    ]
                ),
            ).ask()
            if not value:
                return []
            value_str = str(value)
        else:  # text
            value_result: str | None = questionary.text(arg_prompt).ask()
            if not value_result:
                return []
            value_str = str(value_result)

        # Add to appropriate list based on arg_type
        if arg_arg_type == "option":
            flag: str = str(arg_config.get("flag", f"--{arg_name}"))
            option_args.extend([flag, value_str])
        else:  # positional
            positional_args.append(value_str)

    # Return positional args first, then options
    return positional_args + option_args


def show_group_interactive_menu(group_key: str, group_info: dict) -> None:
    """Show interactive menu for selecting a command within a group using arrow keys.

    Args:
        group_key: The key of the command group (e.g., "db", "users")
        group_info: Dictionary containing group name and commands
    """
    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]{group_info['name']} - Interactive Mode[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print()

    # Prepare choices for questionary
    commands_list = list(group_info["commands"].items())
    choices = [questionary.Choice(title=f"{cmd_key:20s} - {cmd_desc}", value=cmd_key) for cmd_key, cmd_desc in commands_list]

    # Use questionary.select for arrow key navigation
    selected_command = questionary.select(
        "Select command (use ↑↓ arrow keys, Enter to confirm):",
        choices=choices,
        use_arrow_keys=True,
        use_jk_keys=False,
        style=questionary.Style(
            [
                ("qmark", "fg:#673ab7 bold"),  # token in front of the question
                ("question", "bold"),  # question text
                ("answer", "fg:#f44336 bold"),  # submitted answer text behind the question
                ("pointer", "fg:#673ab7 bold"),  # pointer used in select and checkbox prompts
                ("highlighted", "fg:#673ab7 bold"),  # pointed-at choice in select and checkbox prompts
                ("selected", "fg:#cc5454"),  # style for a selected item of a checkbox
                ("separator", "fg:#cc5454"),  # separator in lists
                ("instruction", ""),  # user instructions for select, rawselect, checkbox
                ("text", ""),  # plain text
                ("disabled", "fg:#858585 italic"),  # disabled choices for select and checkbox prompts
            ]
        ),
    ).ask()

    if not selected_command:
        # User cancelled (Ctrl+C)
        console.print("\n[yellow]Cancelled[/yellow]")
        return

    # Check if command requires arguments
    command_path = f"{group_key}.{selected_command}"
    required_args = prompt_for_arguments(command_path)

    # Build command and execute
    console.print()
    if required_args:
        console.print(f"[dim]Executing: [cyan]{group_key} {selected_command} {' '.join(required_args)}[/cyan][/dim]")
    else:
        console.print(f"[dim]Executing: [cyan]{group_key} {selected_command}[/cyan][/dim]")
    console.print()

    # Reconstruct sys.argv to pass to Typer
    # Replace current args with selected command and its arguments
    sys.argv = [sys.argv[0], group_key, selected_command] + required_args

    # Execute the command via Typer
    app()


def _show_interactive_menu() -> None:
    """Show interactive menu for command selection using arrow keys."""
    console.print()
    console.print(Panel.fit("[bold cyan]AI Workspace CLI - Interactive Mode[/bold cyan]", border_style="cyan"))
    console.print()

    # Prepare choices for questionary
    choices = [questionary.Choice(title=f"{group_key:8s} - {group_info['name']}", value=group_key) for group_key, group_info in COMMAND_GROUPS.items()]

    # Use questionary.select for arrow key navigation
    selected_group = questionary.select(
        "Select command group (use ↑↓ arrow keys, Enter to confirm):",
        choices=choices,
        use_arrow_keys=True,
        use_jk_keys=False,
        style=questionary.Style(
            [
                ("qmark", "fg:#673ab7 bold"),  # token in front of the question
                ("question", "bold"),  # question text
                ("answer", "fg:#f44336 bold"),  # submitted answer text behind the question
                ("pointer", "fg:#673ab7 bold"),  # pointer used in select and checkbox prompts
                ("highlighted", "fg:#673ab7 bold"),  # pointed-at choice in select and checkbox prompts
                ("selected", "fg:#cc5454"),  # style for a selected item of a checkbox
                ("separator", "fg:#cc5454"),  # separator in lists
                ("instruction", ""),  # user instructions for select, rawselect, checkbox
                ("text", ""),  # plain text
                ("disabled", "fg:#858585 italic"),  # disabled choices for select and checkbox prompts
            ]
        ),
    ).ask()

    if not selected_group:
        # User cancelled (Ctrl+C)
        console.print("\n[yellow]Cancelled[/yellow]")
        return

    group_info = COMMAND_GROUPS[selected_group]

    # Show commands in selected group using the helper function
    show_group_interactive_menu(selected_group, group_info)


def main() -> None:
    """Main entry point for the CLI."""
    # Initialize Sentry before running CLI (to catch all errors)
    init_sentry()

    # Check if no arguments provided (only script name)
    # If so, show interactive menu
    if len(sys.argv) == 1:
        _show_interactive_menu()
    else:
        # Normal Typer execution with arguments
        app()


if __name__ == "__main__":
    main()
