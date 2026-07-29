"""Billing and subscription management commands."""

import asyncio
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

billing_app = typer.Typer(name="billing", help="Billing & subscription management")

console = Console()

VALID_PLANS = ["free", "pro", "pro_plus"]
PLAN_ALIASES = {"pro+": "pro_plus", "proplus": "pro_plus"}
PLAN_DISPLAY_NAMES = {
    "free": "[dim]Free[/dim]",
    "pro": "[cyan]Pro[/cyan]",
    "pro_plus": "[bold magenta]Pro+[/bold magenta]",
}


@billing_app.callback(invoke_without_command=True)
def billing_callback(ctx: typer.Context) -> None:
    """Billing & subscription management commands."""
    if ctx.invoked_subcommand is None:
        console.print("[yellow]No subcommand provided. Use --help to see available commands.[/yellow]")


@billing_app.command("change-plan")
def billing_change_plan(
    identifier: str | None = typer.Argument(None, help="User email or ID whose plan to change"),
    plan: str | None = typer.Option(
        None,
        "--plan",
        "-p",
        help="Plan tier to set: free, pro, or pro_plus (pro+ accepted as alias)",
    ),
    reason: str | None = typer.Option(
        None,
        "--reason",
        help="Reason for the change (recorded in subscription history)",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Change a user's subscription plan (free, pro, or pro_plus).

    Examples:
        # Interactive mode (will prompt for email/ID and plan)
        python -m cli billing change-plan

        # Change plan by email
        python -m cli billing change-plan user@example.com --plan pro

        # Non-interactive (for scripts)
        python -m cli billing change-plan user@example.com \\
            --plan pro_plus --reason "Manual upgrade" --yes
    """
    asyncio.run(_billing_change_plan_async(identifier, plan, reason, yes))


async def _billing_change_plan_async(identifier: str | None, plan: str | None, reason: str | None, yes: bool) -> None:
    """Async implementation of plan change."""
    from cli.commands.users import _find_user

    try:
        if not identifier:
            identifier = Prompt.ask("[cyan]Enter user email or ID[/cyan]")

        with console.status("[bold green]Finding user...", spinner="dots"):
            user = await _find_user(identifier)

        if not user:
            console.print(f"\n[red]User not found:[/red] {identifier}\n")
            return

        with console.status("[bold green]Loading subscription...", spinner="dots"):
            subscription = await _get_or_create_subscription(user["id"])

        if not plan:
            console.print("\n[bold cyan]Available plans:[/bold cyan]\n")
            for i, plan_option in enumerate(VALID_PLANS, 1):
                console.print(f"  {i}. {PLAN_DISPLAY_NAMES[plan_option]}")
            console.print()

            while True:
                plan_input = Prompt.ask("[cyan]Select plan[/cyan] (1-3 or name)", default="").strip().lower()

                if plan_input.isdigit():
                    plan_num = int(plan_input)
                    if 1 <= plan_num <= len(VALID_PLANS):
                        plan = VALID_PLANS[plan_num - 1]
                        break
                    console.print(f"[red]Invalid number. Please enter 1-{len(VALID_PLANS)}[/red]")
                    continue

                normalized = PLAN_ALIASES.get(plan_input, plan_input)
                if normalized in VALID_PLANS:
                    plan = normalized
                    break

                console.print(f"[red]Invalid plan. Please enter 1-{len(VALID_PLANS)} or one of: {', '.join(VALID_PLANS)}[/red]")
        else:
            normalized = PLAN_ALIASES.get(plan.lower().strip(), plan.lower().strip())
            if normalized not in VALID_PLANS:
                console.print(f"\n[red]Invalid plan:[/red] {plan}\n")
                console.print(f"[yellow]Valid plans are:[/yellow] {', '.join(VALID_PLANS)}\n")
                raise typer.Exit(1)
            plan = normalized

        if plan == subscription["planTier"]:
            console.print(f"\n[yellow]User is already on plan {PLAN_DISPLAY_NAMES[plan]}[/yellow]\n")
            return

        console.print("\n[bold cyan]Subscription to modify:[/bold cyan]\n")

        plan_info = f"""[bold]ID:[/bold] {user['id']}
[bold]Email:[/bold] {user['email']}
[bold]Name:[/bold] {user['name']}
[bold]Current Plan:[/bold] {PLAN_DISPLAY_NAMES[subscription['planTier']]}
[bold]New Plan:[/bold] {PLAN_DISPLAY_NAMES[plan]}"""

        panel = Panel(plan_info, border_style="cyan")
        console.print(panel)

        if not yes:
            console.print()
            if not Confirm.ask(f"Are you sure you want to change the plan to {PLAN_DISPLAY_NAMES[plan]}?", default=True):
                console.print("[yellow]Cancelled[/yellow]")
                return

        with console.status("[bold green]Updating subscription...", spinner="dots"):
            await _update_plan_in_db(subscription["id"], plan, reason)

        console.print(f"\n[bold green]✓[/bold green] Plan changed to {PLAN_DISPLAY_NAMES[plan]} successfully\n")

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"\n[red]Error changing plan:[/red] {e}\n")
        raise typer.Exit(1) from None


async def _get_or_create_subscription(user_id: str) -> dict[str, Any]:
    """Get a user's subscription, auto-creating a free-tier one if it doesn't exist yet.

    Mirrors BillingService.get_subscription, used by the app's own subscription views.

    Args:
        user_id: User ID

    Returns:
        dict: Subscription id and current plan tier
    """
    from app.core.database import get_db
    from app.modules.billing.dependencies import get_stripe_client
    from app.modules.billing.repository import BillingRepository
    from app.modules.billing.service import BillingService

    async for db in get_db():
        service = BillingService(repository=BillingRepository(db), stripe_client=get_stripe_client())
        subscription = await service.get_subscription(user_id)
        return {"id": subscription.id, "planTier": subscription.planTier}

    raise RuntimeError("Database session unavailable")


async def _update_plan_in_db(subscription_id: str, plan_tier: str, reason: str | None) -> None:
    """Update a subscription's plan tier, mirroring the admin panel's update logic.

    Args:
        subscription_id: Subscription ID
        plan_tier: New plan tier
        reason: Optional reason recorded in the subscription history audit trail
    """
    from app.core.database import get_db
    from app.modules.billing.dependencies import get_stripe_client
    from app.modules.billing.repository import BillingRepository
    from app.modules.billing.service import BillingService

    async for db in get_db():
        service = BillingService(repository=BillingRepository(db), stripe_client=get_stripe_client())
        await service.admin_update_subscription(
            subscription_id=subscription_id,
            plan_tier=plan_tier,
            reason=reason,
        )
        break
