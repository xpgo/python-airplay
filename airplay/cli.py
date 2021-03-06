import os
import os.path
import platform
import time
import sys
import traceback
import urllib
import tempfile

from airplay import AirPlay

import click


def get_airplay_device(hostport):
    if hostport is not None:
        try:
            (host, port) = hostport.split(':', 1)
            port = int(port)
        except ValueError:
            host = hostport
            port = 7000

        return AirPlay(host, port)

    devices = AirPlay.find(fast=True)

    if len(devices) == 0:
        return None
    elif len(devices) == 1:
        return devices[0]
    elif len(devices) > 1:
        error = "Multiple AirPlay devices were found.  Use --device to select a specific one.\n\n"
        error += "Available AirPlay devices:\n"
        error += "--------------------\n"
        for dd in devices:
            error += "\t* {0}: {1}:{2}\n".format(dd.name, dd.host, dd.port)

        raise RuntimeError(error)


def humanize_seconds(secs):
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)

    return "%02d:%02d:%02d" % (h, m, s)


@click.group()
def main():
    pass


@main.command()
def discover():
    """Discover AirPlay devices in connected network"""
    click.echo("AirPlay device discover start...")
    devices = AirPlay.find(fast=True)
    if not devices or len(devices) == 0:
        click.echo("There's no AirPlay device in your network.")
    else:
        click.echo("AirPlay device discover complete!")
        for dd in devices:
            click.echo("\t %s\t %s:%s\n" % (dd.name, dd.host, dd.port))


@main.command()
@click.option('-t', '--time', 'duration', metavar='<time>', type=int, default=10, help='display duration(seconds)')
@click.option('-d', '--dev', '--device', metavar='<host/ip>[:<port>]')
@click.argument('path', metavar='<path/url>')
def photo(path, device, duration):
    """AirPlay a photo"""
    data = None
    if path.startswith('http'):
        data = urllib.urlopen(path).read()
    elif os.path.exists(path) and os.path.isfile(path):
        data = open(path, 'r').read()

    if data is None:
        click.secho("photo not exists!", fg="red", err=True)
        sys.exit(-1)
    ap = None
    try:
        ap = get_airplay_device(device)
    except (ValueError, RuntimeError) as exc:
        traceback.print_exc()

    if not ap:
        click.secho("No AirPlay devices found in your network!", fg="red", err=True)
        sys.exit(-1)

    ap.photo(data)
    if time >0:
        with click.progressbar(range(0, duration)) as bar:
            for i in bar:
                time.sleep(1)
        ap.stop()


@main.command()
@click.option('-t', '--time', 'duration', metavar='<time>', type=click.IntRange(10, 999999, clamp=True), default=60, help='screen cast duration(seconds)')
@click.option('-d', '--dev', '--device', metavar='<host/ip>[:<port>]')
def screen(duration, device):
    """AirPlay screen cast(without voice yet)"""
    is_linux = False
    sysstr = platform.system()
    if(sysstr == "Linux"):
        is_linux = True
    else:
        from PIL import ImageGrab
    ap = None
    try:
        ap = get_airplay_device(device)
    except (ValueError, RuntimeError) as exc:
        traceback.print_exc()

    if not ap:
        click.secho("No AirPlay devices found in your network!", fg="red", err=True)
        sys.exit(-1)

    path = tempfile.gettempdir()
    #scrot screen.png
    fn = os.path.join(path, "screen.png")
    start = round(time.time())
    while round(time.time()) - start < duration:
        if is_linux:
            os.system('scrot -z ' + fn)
        else:
            ImageGrab.grab().save(fn, "png")
        
        data = open(fn, 'r').read()

        ap.photo(data)
    ap.stop()


@main.command()
@click.argument('path', metavar='<path/url>')
@click.option('-p', '--pos', '--position', metavar="<position>", default=0, type=float)
@click.option('-d', '--dev', '--device', metavar="<host/ip>[:<port>]")
def video(path, position, device):
    """AirPlay a video"""
    #connect to the AirPlay device we want to control
    ap = None
    try:
        ap = get_airplay_device(device)
    except (ValueError, RuntimeError) as exc:
        traceback.print_exc()

    if not ap:
        click.secho("No AirPlay devices found in your network!", fg="red", err=True)
        sys.exit(-1)

    duration = 0
    state = 'loading'

    # if the url is on our local disk, then we need to spin up a server to start it
    if os.path.exists(path):
        path = ap.serve(path)

    # play what they asked
    ap.play(path, position)

    # stay in this loop until we exit
    with click.progressbar(length=100, show_eta=False) as bar:
        try:
            while True:
                for ev in ap.events(block=False):
                    newstate = ev.get('state', None)

                    if newstate is None:
                        continue

                    if newstate == 'playing':
                        duration = ev.get('duration')
                        position = ev.get('position')

                    state = newstate

                if state == 'stopped':
                    raise KeyboardInterrupt

                bar.label = state.capitalize()

                if state == 'playing':
                    info = ap.scrub()
                    duration = info['duration']
                    position = info['position']

                if state in ['playing', 'paused']:
                    bar.label += ': {0} / {1}'.format(
                        humanize_seconds(position),
                        humanize_seconds(duration)
                    )
                    try:
                        bar.pos = int((position / duration) * 100)
                    except ZeroDivisionError:
                        bar.pos = 0

                bar.label = bar.label.ljust(28)
                bar.render_progress()

                time.sleep(.5)

        except KeyboardInterrupt:
            ap = None
            raise SystemExit


if __name__ == '__main__':
    main()
