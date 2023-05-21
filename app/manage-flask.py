# manage.py
import click


from app import app, DeviceMeasurement



@app.cli.command("show-data")
@click.argument("name")
def show_data(name):
    click.echo(f"Hello, {name}!")
    with app.app_context():
        measurements = DeviceMeasurement.query.filter_by(name=name)
        for m in measurements:
            click.echo(f"solar_energy={m.solar_energy} solar_consumed_energy={m.solar_consumed_energy} date={m.date}")


if __name__ == '__main__':
    cli()
