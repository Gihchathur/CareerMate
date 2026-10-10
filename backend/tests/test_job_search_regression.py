from app.models.job import JobPosting
from app.services import job_discovery
from app.services.job_sources import jobtech_links


def posting(**overrides):
    payload = dict(
        id='jobtech-links:1', source='jobtech_links', source_id='1',
        title='Software Engineer', company='Example AB',
        location='Location not specified', description='Build software',
        published_at='2026-10-01', source_url='https://example.com/jobs/1',
        apply_url='https://example.com/jobs/1', city='', country='',
        work_mode='unknown', search_roles=[]
    )
    payload.update(overrides)
    return JobPosting(**payload)


def test_city_filter_keeps_jobtech_result_with_missing_location(monkeypatch):
    job = posting()
    monkeypatch.setattr(job_discovery, 'search_jobs', lambda **kwargs: (66, [job]))
    result = job_discovery.search_multiple_roles(
        roles=['Software Engineer'], country='Any country', city='Stockholm',
        work_mode='any', limit=10, offset=0, sources=['jobtech_links'],
    )
    assert result['total_reported'] == 66
    assert result['returned'] == 1
    assert result['jobs'][0].title == 'Software Engineer'


def test_city_filter_still_rejects_structured_city_mismatch(monkeypatch):
    job = posting(city='Gothenburg', location='Gothenburg, Sweden', country='Sweden')
    monkeypatch.setattr(job_discovery, 'search_jobs', lambda **kwargs: (66, [job]))
    result = job_discovery.search_multiple_roles(
        roles=['Software Engineer'], country='Any country', city='Stockholm',
        work_mode='any', limit=10, offset=0, sources=['jobtech_links'],
    )
    assert result['returned'] == 0
    assert result['filtered_out_by']['city'] == 1


def test_remote_listing_with_generic_location_can_be_kept(monkeypatch):
    job = posting(id='remoteok:1', source='remoteok', source_id='1', location='Remote', city='', country='', work_mode='remote')
    monkeypatch.setattr(job_discovery, 'fetch_remote_jobs', lambda: [job])
    result = job_discovery.search_multiple_roles(
        roles=['Software Engineer'], country='Any country', city='Stockholm',
        work_mode='any', limit=10, offset=0, sources=['remoteok'],
    )
    assert result['returned'] == 1


def test_jobtech_normalizer_handles_wrapped_hit():
    result = jobtech_links.normalize_job({
        '_id': 'example-123',
        '_source': {
            'headline': 'Software Engineer',
            'employer': {'name': 'Example AB'},
            'workplace_address': {'municipality': 'Stockholm', 'country': 'Sweden'},
            'source_links': [{'url': 'https://example.com/job/123'}],
            'brief': 'Build software services',
        },
    })
    assert result.source_id == 'example-123'
    assert result.title == 'Software Engineer'
    assert result.company == 'Example AB'
    assert result.city == 'Stockholm'
    assert result.source_url == 'https://example.com/job/123'


def test_jobtech_search_accepts_nested_hits_shape(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None
        def json(self):
            return {
                'hits': {
                    'total': {'value': 8},
                    'hits': [{
                        '_id': 'nested-1',
                        '_source': {
                            'headline': 'Software Engineer',
                            'employer': {'name': 'Example AB'},
                            'workplace_address': {'municipality': 'Stockholm'},
                            'source_links': [{'url': 'https://example.com/job/1'}],
                        },
                    }],
                }
            }
    monkeypatch.setattr(jobtech_links, 'get_with_retries', lambda *a, **kw: FakeResponse())
    total, jobs = jobtech_links.search_jobs('Software Engineer Stockholm', limit=10, offset=0)
    assert total == 8
    assert len(jobs) == 1
    assert jobs[0].title == 'Software Engineer'
    assert jobs[0].city == 'Stockholm'
