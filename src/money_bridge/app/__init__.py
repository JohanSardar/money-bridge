import typer

cli = typer.Typer(name="moneybridge", no_args_is_help=True)


@cli.command()
def version() -> None:
    from importlib.metadata import version as installed_version

    typer.echo(installed_version("money-bridge"))


def main() -> None:
    cli()
