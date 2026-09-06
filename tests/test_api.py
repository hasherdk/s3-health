from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

import api


@pytest.fixture
def client():
    return TestClient(api.app)


@pytest.fixture
def s3(monkeypatch):
    fake = Mock()
    fake.get_paginator.return_value.paginate.return_value = []
    monkeypatch.setattr(api, 'get_s3_client', lambda: fake)
    return fake


@pytest.mark.parametrize('value, expected', [
    (None, timedelta(hours=24)), ('30m', timedelta(minutes=30)),
    ('12h', timedelta(hours=12)), ('2d', timedelta(days=2)),
])
def test_duration(value, expected):
    assert api.parse_duration(value) == expected


@pytest.mark.parametrize('value', ['abc', '-1h', '1w', '1.5h'])
def test_invalid_duration(value):
    with pytest.raises(ValueError):
        api.parse_duration(value)


@pytest.mark.parametrize('value, expected', [
    ('true', True), (' YES ', True), ('1', True), ('on', True),
    ('false', False), (' OFF ', False), ('0', False), ('no', False),
    ('invalid', True),
])
def test_bool_env(monkeypatch, value, expected):
    monkeypatch.setenv('S3_VERIFY_TLS', value)
    assert api.parse_bool_env('S3_VERIFY_TLS') is expected


def test_s3_configuration(monkeypatch):
    factory = Mock()
    monkeypatch.setattr(api.boto3, 'client', factory)
    for name in ['S3_KEY', 'S3_SECRET', 'S3_ENDPOINT', 'S3_VERIFY_TLS']:
        monkeypatch.delenv(name, raising=False)
    api.get_s3_client()
    assert factory.call_args.kwargs['verify'] is True
    assert factory.call_args.kwargs['endpoint_url'] == 'https://s3.amazonaws.com'
    monkeypatch.setenv('S3_ENDPOINT', 'https://minio.example')
    monkeypatch.setenv('S3_KEY', 'test-key')
    monkeypatch.setenv('S3_SECRET', 'test-secret')
    monkeypatch.setenv('S3_VERIFY_TLS', 'false')
    api.get_s3_client()
    factory.assert_called_with('s3', endpoint_url='https://minio.example',
                               aws_access_key_id='test-key',
                               aws_secret_access_key='test-secret', verify=False)


def test_health_requires_no_s3(client, monkeypatch):
    monkeypatch.setattr(api, 'get_s3_client', Mock(side_effect=AssertionError))
    assert client.get('/health').json() == {'status': 'ok'}


def test_freshness_pagination(client, s3):
    now = datetime.now(timezone.utc)
    s3.get_paginator.return_value.paginate.return_value = [
        {'Contents': [{'Key': 'old', 'LastModified': now - timedelta(days=3)}]},
        {}, {'Contents': [{'Key': 'new', 'LastModified': now - timedelta(minutes=1)}]},
    ]
    response = client.get('/buckets/backups/freshness?max_age=1h')
    assert response.status_code == 200
    assert response.json()['newest_object']['key'] == 'new'
    s3.get_paginator.return_value.paginate.assert_called_with(Bucket='backups')


def test_stale_and_unrestricted_freshness(client, s3):
    s3.get_paginator.return_value.paginate.return_value = [{'Contents': [
        {'Key': 'old', 'LastModified': datetime.now(timezone.utc) - timedelta(days=3)}
    ]}]
    assert client.get('/buckets/b/freshness').status_code == 200
    response = client.get('/buckets/b/freshness?max_age=1d')
    assert response.status_code == 500
    assert 'too old' in response.json()['detail']['reason']


def test_empty_bucket(client, s3):
    assert client.get('/buckets/b/freshness').status_code == 500
    assert client.get('/buckets/b/usage').json()['usage']['object_count'] == 0


def test_invalid_age(client, s3):
    assert client.get('/buckets/b/freshness?max_age=invalid').status_code == 422


@pytest.mark.parametrize('size, formatted', [(1048576, '1.00 MB'), (1073741824, '1.00 GB')])
def test_usage(client, s3, size, formatted):
    s3.get_paginator.return_value.paginate.return_value = [
        {'Contents': [{'Key': 'a', 'Size': size}]},
        {'Contents': [{'Key': 'b'}]},
    ]
    result = client.get('/buckets/b/usage')
    assert result.status_code == 200
    assert result.json()['usage'] == {
        'object_count': 2, 'total_size_bytes': size, 'total_size_formatted': formatted,
    }


@pytest.mark.parametrize('endpoint', ['usage', 'freshness'])
@pytest.mark.parametrize('code', ['AccessDenied', 'NoSuchBucket'])
def test_s3_error(client, s3, endpoint, code):
    s3.get_paginator.return_value.paginate.side_effect = ClientError(
        {'Error': {'Code': code, 'Message': 'test failure'}}, 'ListObjectsV2')
    response = client.get(f'/buckets/b/{endpoint}')
    assert response.status_code == 500
    assert response.json()['detail']['status'] == 'fail'
    if code == 'AccessDenied':
        assert 's3:ListBucket' in response.json()['detail']['reason']
