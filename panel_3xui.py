import datetime
import logging
import sys
import uuid

from decouple import config
from py3xui import Api, Client

inbound_id = 2

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
    expiry_time = int((datetime.datetime.now() + expiry_delta).timestamp()) * 1000
    new_client = Client(id=uuid_str, email=name, enable=True,
                        limit_ip=limit_ip, expiry_time=expiry_time,
                        flow="xtls-rprx-vision", total_gb=total_gb)
    api.client.add(inbound_id, [new_client])


def delete_client(api, name):
    inbound, nc = get_client_and_inbound_by_email(api, name)
    try:
        api.client.delete(inbound.id, nc.id)
    except AttributeError:
        print("Client does not exist")


def get_client_url(api, name):
    inbound, nc = get_client_and_inbound_by_email(api, name)
    print(inbound)
    config_ufl = f"""{inbound.protocol}://{nc.id}@{get_address()}:{inbound.port}?type={inbound.stream_settings.network}&security={inbound.stream_settings.security}&pbk={inbound.stream_settings.reality_settings['settings']['publicKey']}&fp={inbound.stream_settings.reality_settings['settings']['fingerprint']}&sni={inbound.stream_settings.reality_settings['serverNames'][0]}&sid={inbound.stream_settings.reality_settings['shortIds'][0]}&flow={nc.flow}&spx=%2F#KOVANOFF-VPN"""
    print(config_ufl)
    return config_ufl


if __name__ == "__main__":
    panel_uuid = uuid.uuid4()
    api = login()
    add_client(api, panel_uuid, 2, datetime.timedelta(hours=1))
    get_client_url(api, panel_uuid)
