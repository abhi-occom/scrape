import unittest
from unittest.mock import MagicMock, patch

from isp.main_crawler import CrawlResult, ISPCrawler
from providers.aussie import scrape_aussie_plans
from utils.db import insert_plans_batch


class AussieNetworkTests(unittest.TestCase):
    def test_provider_returns_only_nbn_and_opticomm(self):
        plans = scrape_aussie_plans()

        self.assertEqual(13, len(plans))
        self.assertEqual({'NBN', 'Opticomm'}, {p['network_type'] for p in plans})
        self.assertFalse(any(
            token in p['network_type'].lower()
            for p in plans
            for token in ('redtrain', 'supa')
        ))

    @patch('scraper_service.scrape_provider')
    def test_crawler_filters_unsupported_aussie_fallback_networks(self, scrape_provider):
        valid_plan = {
            'provider': 'Aussie Broadband',
            'network_type': 'NBN',
            'plan_name': 'Valid NBN',
            'download_speed': 50,
            'upload_speed': 20,
            'price': 80,
        }
        invalid_plan = {
            **valid_plan,
            'network_type': 'Supa',
            'plan_name': 'Invalid Supa',
        }
        scrape_provider.return_value = {
            'success': True,
            'plans': [valid_plan, invalid_plan],
        }
        crawler = ISPCrawler(
            'https://www.aussiebroadband.com.au/internet/nbn-plans/',
            network_types=['nbn', 'opticomm', 'redtrain', 'supa'],
        )
        result = CrawlResult(
            base_url=crawler.base_url,
            provider_name='Aussie Broadband',
        )

        crawler._try_provider_fallback(result)

        self.assertTrue(result.success)
        self.assertEqual(['NBN'], result.network_types_found)
        self.assertEqual(['Valid NBN'], [p['plan_name'] for p in result.plans])

    @patch('scraper_service.scrape_provider')
    def test_other_provider_can_keep_supported_supa_plans(self, scrape_provider):
        supa_plan = {
            'provider': 'Occom',
            'network_type': 'Supa',
            'plan_name': 'Occom Supa',
            'download_speed': 50,
            'upload_speed': 20,
            'price': 80,
        }
        scrape_provider.return_value = {
            'success': True,
            'plans': [supa_plan],
        }
        crawler = ISPCrawler(
            'https://occom.com.au/supa-network-plans/',
            network_types=['supa'],
        )
        result = CrawlResult(base_url=crawler.base_url, provider_name='Occom')

        crawler._try_provider_fallback(result)

        self.assertTrue(result.success)
        self.assertEqual(['Supa'], result.network_types_found)


class DatabaseReplacementTests(unittest.TestCase):
    def test_batch_replaces_provider_inside_single_transaction(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        plans = [{
            'provider_id': 3,
            'plan_name': 'Aussie Broadband NBN Value 50/20',
            'network_type': 'NBN',
            'download_speed': 50,
            'upload_speed': 20,
            'price': 93.0,
        }]

        success = insert_plans_batch(connection, plans, replace_provider_ids={3})

        self.assertTrue(success)
        cursor.execute.assert_called_once_with(
            'DELETE FROM plans_current WHERE provider_id IN (%s)',
            (3,),
        )
        cursor.executemany.assert_called_once()
        connection.commit.assert_called_once()
        connection.rollback.assert_not_called()

    def test_batch_rolls_back_delete_when_insert_fails(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.executemany.side_effect = __import__('mysql.connector').connector.Error(
            'insert failed'
        )

        success = insert_plans_batch(
            connection,
            [{'provider_id': 3, 'plan_name': 'Broken'}],
            replace_provider_ids={3},
        )

        self.assertFalse(success)
        connection.rollback.assert_called_once()
        connection.commit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
