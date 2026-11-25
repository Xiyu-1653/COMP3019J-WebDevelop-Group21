import unittest
from unittest.mock import MagicMock, patch
from reservation_management import allocation, collection, expiration, queue

class ReservationTests(unittest.TestCase):
    def test_waiting_queue_positions_renumber_from_one(self):
        c=MagicMock(); c.fetchall.return_value=[
            {'reservation_id':3,'username':'frank'},
            {'reservation_id':4,'username':'grace'},
        ]
        rows=queue.get_waiting_queue(c,2)
        self.assertEqual([r['queue_position'] for r in rows],[1,2])
        self.assertEqual([r['reservation_id'] for r in rows],[3,4])

    def test_reservation_history_filters_status_and_keyword(self):
        c=MagicMock(); c.fetchall.return_value=[{'reservation_id':2}]
        rows=queue.get_reservation_history(c,status='expired',keyword='alice')
        self.assertEqual(rows,[{'reservation_id':2}])
        sql,params=c.execute.call_args.args
        self.assertIn('r.status = %s',sql)
        self.assertIn('u.username LIKE %s',sql)
        self.assertEqual(params,['expired','%alice%','%alice%',200])

    def test_reservation_history_ignores_unknown_status(self):
        c=MagicMock(); c.fetchall.return_value=[]
        queue.get_reservation_history(c,status='bogus')
        sql,params=c.execute.call_args.args
        self.assertNotIn('WHERE',sql)
        self.assertEqual(params,[200])

    def test_allocate_available_copy_and_notify(self):
        c=MagicMock(); c.fetchone.side_effect=[{'title_id':1,'status':'available'},{'config_value':'3'}]
        with patch.object(allocation,'get_first_waiting_reservation',return_value={'reservation_id':7,'reader_id':2}) as head:
            self.assertEqual(allocation.allocate_available_copy(c,4),7)
            head.assert_called_once_with(c,1,lock=True)
        sql=' '.join(x.args[0] for x in c.execute.call_args_list)
        self.assertIn("status = 'ready'",sql); self.assertIn("status = 'reserved'",sql)
        self.assertIn('INSERT INTO notification',sql)

    def test_allocation_rejects_missing_or_unavailable_copy(self):
        for row in [None,{'status':'borrowed'},{'status':'reserved'}]:
            with self.subTest(row=row):
                c=MagicMock(); c.fetchone.return_value=row
                self.assertIsNone(allocation.allocate_available_copy(c,4))
                self.assertEqual(c.execute.call_count,1)

    def test_allocation_with_empty_queue_does_not_write(self):
        c=MagicMock(); c.fetchone.return_value={'title_id':1,'status':'available'}
        with patch.object(allocation,'get_first_waiting_reservation',return_value=None):
            self.assertIsNone(allocation.allocate_available_copy(c,4))
        self.assertEqual(c.execute.call_count,1)

    def test_allocation_requires_configuration(self):
        c=MagicMock(); c.fetchone.side_effect=[{'title_id':1,'status':'available'},None]
        with patch.object(allocation,'get_first_waiting_reservation',return_value={'reservation_id':7}):
            with self.assertRaisesRegex(ValueError,'configuration'): allocation.allocate_available_copy(c,4)

    def test_collect_ready_reservation(self):
        c=MagicMock(); c.fetchone.return_value={'reader_id':2,'allocated_copy_id':4}; c.lastrowid=42
        with patch.object(collection,'process_expired_reservations') as expire:
            self.assertEqual(collection.collect_reservation(c,7,1,14),42)
            expire.assert_called_once_with(c)
        insert=[x for x in c.execute.call_args_list if 'INSERT INTO loan' in x.args[0]][0]
        self.assertEqual(insert.args[1],(2,4,1,14))
        sql=' '.join(x.args[0] for x in c.execute.call_args_list)
        self.assertIn("status = 'fulfilled'",sql); self.assertIn('allocated_copy_id = NULL',sql)
        self.assertIn("status = 'borrowed'",sql)

    def test_collect_nonready_reservation_rejected(self):
        c=MagicMock(); c.fetchone.return_value=None
        with patch.object(collection,'process_expired_reservations'):
            with self.assertRaises(collection.ReservationError): collection.collect_reservation(c,7,1,14)
        self.assertEqual(c.execute.call_count,1)

    def test_expiration_requires_configuration(self):
        c=MagicMock(); c.fetchone.return_value=None
        with self.assertRaises(ValueError): expiration.process_expired_reservations(c)

    def test_no_expired_reservations_makes_no_updates(self):
        c=MagicMock(); c.fetchone.return_value={'config_value':'3'}; c.fetchall.return_value=[]
        self.assertEqual(expiration.process_expired_reservations(c),0)
        self.assertEqual(c.execute.call_count,2)

    def test_expired_copy_released_or_passed_to_queue_head(self):
        for next_reader in [None,{'reservation_id':8,'reader_id':3}]:
            with self.subTest(next_reader=next_reader):
                c=MagicMock(); c.fetchone.return_value={'config_value':'3'}
                c.fetchall.return_value=[{'reservation_id':7,'reader_id':2,'title_id':1,'allocated_copy_id':4}]
                with patch.object(expiration,'get_first_waiting_reservation',return_value=next_reader):
                    self.assertEqual(expiration.process_expired_reservations(c),1)
                sql=' '.join(x.args[0] for x in c.execute.call_args_list)
                self.assertIn("status = 'expired'",sql)
                self.assertIn("status = 'ready'" if next_reader else "status = 'available'",sql)
                notices=[x for x in c.execute.call_args_list if 'INSERT INTO notification' in x.args[0]]
                self.assertEqual(len(notices),2 if next_reader else 1)
