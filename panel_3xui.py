import datetime
import logging
import sys
import traceback
import uuid

from decouple import config
from py3xui import Api, Client

from headers import tz

logging.basicConfig(level=logging.INFO, stream=sys.stdout)


def get_address():
    return config("XUI_HOST").split(":")[1].replace("//", "")


def login():
    api = Api(config("XUI_HOST"), config("XUI_USERNAME"), config("XUI_PASSWORD"), use_tls_verify=False)
    api.login()
    return api


def get_inbounds(api):
    inbounds = api.inbound.get_list()
    return inbounds


def get_inbound(api, inbound_id):
    inbounds = get_inbounds(api)
    for inbound in inbounds:
        if inbound.id == inbound_id:
            return inbound


def get_client_and_inbound_by_email(api, name):
    inbounds = get_inbounds(api)
    for inbound in inbounds:
        for user in inbound.settings.clients:
            if name == user.email:
                return inbound, user


def add_client(api, name, limit_ip: int, expiry_delta: datetime.timedelta, total_gb=0):
    '''
    :param api:
    :param name:
    :param limit_ip:
    :param expiry_delta:
    :param total_gb:
    :return:
    '''
    name = str(name)
    uuid_str = str(uuid.uuid4())
    expiry_time = int((datetime.datetime.now(tz) + expiry_delta).timestamp()) * 1000
    new_client = Client(id=uuid_str, email=name, enable=True,
                        limit_ip=limit_ip, expiry_time=expiry_time,
                        flow="xtls-rprx-vision", total_gb=total_gb * (1024 ** 3))
    api.client.add(2, [new_client])


def delete_client(api, name):
    try:
        inbound, nc = get_client_and_inbound_by_email(api, name)
        api.client.delete(inbound.id, nc.id)
        return True
    except TypeError:
        print(f"Client does not exist: {name=}")
        return False
    except Exception:
        traceback.print_exc()
        return False


def get_client_url(api, name):
    inbound, nc = get_client_and_inbound_by_email(api, name)
    config_ufl = f"""{inbound.protocol}://{nc.id}@{get_address()}:{inbound.port}?type={inbound.stream_settings.network}&security={inbound.stream_settings.security}&pbk={inbound.stream_settings.reality_settings['settings']['publicKey']}&fp={inbound.stream_settings.reality_settings['settings']['fingerprint']}&sni={inbound.stream_settings.reality_settings['serverNames'][0]}&sid={inbound.stream_settings.reality_settings['shortIds'][0]}&flow={nc.flow}&spx=%2F#KOVANOFF-VPN"""
    return config_ufl


def continue_client(api, name, new_expiredate):
    _, nc = get_client_and_inbound_by_email(api, name)
    client = api.client.get_by_email(name)
    client.expiry_time = int(new_expiredate.timestamp()) * 1000
    client.id = nc.id
    api.client.update(nc.id, client)


if __name__ == "__main__":
    api = login()
    add_client(api, '526', 2, datetime.timedelta(hours=2), 52)


