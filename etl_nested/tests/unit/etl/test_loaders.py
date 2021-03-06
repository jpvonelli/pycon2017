import logging

import pytest
import sqlalchemy.inspection as sa_inspection
import sqlalchemy.orm as sa_orm

from app import models, factories
from app.etl.loaders import chunked_bulk_insert_mappings


@pytest.fixture(scope='module')
def comparable_properties():
    mapper = sa_inspection.inspect(models.ResponseEvent)
    return [column.key for column in mapper.attrs if column.key != 'id']


@pytest.mark.parametrize('num_events', [
    0,
    1,
    2,
    10,
    100
])
def test_loader_insertion(session: sa_orm.Session, loader,
                          comparable_properties, num_events, mock_logger):
    expected_events = factories.ResponseEventFactory.build_batch(num_events)
    loader(expected_events)
    session.flush()
    expected_events = sorted(expected_events, key=lambda e: e.id)

    # verify that the correct number of events were inserted
    inserted_events = session.query(models.ResponseEvent).order_by('id').all()
    assert len(inserted_events) == num_events

    # sanity check
    assert comparable_properties

    # verify that individual properties were inserted correctly
    for i in range(num_events):
        for k in comparable_properties:
            expected_event = expected_events[i]
            actual_event = inserted_events[i]
            assert getattr(actual_event, k) == getattr(expected_event, k)

    # verify the aggregate summary log record
    assert len(mock_logger.messages) == 1
    summary_record = mock_logger.messages[0]
    assert summary_record.level == logging.INFO
    assert summary_record.msg == 'Inserted %d response events into database'
    assert summary_record.args
    assert summary_record.args[0] == num_events


@pytest.mark.parametrize('num_events', [
    0,
    1,
    2,
    10,
    100
])
def test_bulk_insert_mappings(session: sa_orm.Session, comparable_properties, num_events, mock_logger):
    expected_events = factories.ResponseEventFactory.build_batch(num_events)
    expected_events = [
        {
            c.name: getattr(e, c.name)
            for c in e.__table__.columns if c.name != 'id'
        } for e in expected_events
    ]
    chunked_bulk_insert_mappings(session, expected_events, chunk_size=10, return_defaults=True)
    session.flush()
    expected_events = sorted(expected_events, key=lambda e: e['id'])

    # verify that the correct number of events were inserted
    inserted_events = session.query(models.ResponseEvent).order_by('id').all()
    assert len(inserted_events) == num_events

    # sanity check
    assert comparable_properties

    # verify that individual properties were inserted correctly
    for i in range(num_events):
        for k in comparable_properties:
            expected_event = expected_events[i]
            actual_event = inserted_events[i]
            assert getattr(actual_event, k) == expected_event.get(k)

    # verify the aggregate summary log record
    assert len(mock_logger.messages) == 1
    summary_record = mock_logger.messages[0]
    assert summary_record.level == logging.INFO
    assert summary_record.msg == 'Inserted %d response events into database'
    assert summary_record.args
    assert summary_record.args[0] == num_events
