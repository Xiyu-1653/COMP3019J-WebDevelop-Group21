import unittest
from unittest.mock import MagicMock, patch
from borrow_return import service

class BorrowReturnTests(unittest.TestCase):
    def cursor(self, category='undergraduate', loans=None, fee=None):
        c = MagicMock()
        c.fetchone.side_effect = [{'reader_category': category}, fee]
        c.fetchall.return_value = loans or []
        return c

    def test_successful_borrow_uses_category_terms(self):
        for category, days in [('undergraduate',14),('postgraduate',30),('teaching_staff',60)]:
            with self.subTest(category=category):
                c=self.cursor(category)
                service._issue_loan(c,2,9,{'copy_id':1,'title_id':1,'status':'available'})
                insert=[x for x in c.execute.call_args_list if 'INSERT INTO loan' in x.args[0]]
                self.assertEqual(insert[0].args[1],(2,1,9,days))
                self.assertIn("status = 'borrowed'",c.execute.call_args.args[0])

    def test_invalid_reader_rejected(self):
        c=MagicMock(); c.fetchone.return_value=None
        with self.assertRaisesRegex(service.DeskError,'valid reader'):
            service._issue_loan(c,999,9,{'status':'available'})

    def test_nonavailable_statuses_rejected(self):
        for status in ['borrowed','reserved','damaged','lost','under_repair']:
            with self.subTest(status=status):
                with self.assertRaisesRegex(service.DeskError,'unavailable'):
                    service._issue_loan(self.cursor(),2,9,{'status':status})

    def test_overdue_reader_rejected(self):
        c=self.cursor(loans=[{'title_id':3,'overdue':1}])
        with self.assertRaisesRegex(service.DeskError,'overdue'):
            service._issue_loan(c,2,9,{'status':'available'})

    def test_unpaid_fee_rejected(self):
        with self.assertRaisesRegex(service.DeskError,'unpaid'):
            service._issue_loan(self.cursor(fee={'exists':1}),2,9,{'status':'available'})

    def test_distinct_title_limit_boundaries(self):
        for category, limit in [('undergraduate',5),('postgraduate',10),('teaching_staff',10)]:
            for count,title,allowed in [(limit-1,999,True),(limit,999,False),(limit,1,True)]:
                with self.subTest(category=category,count=count,title=title):
                    c=self.cursor(category,[{'title_id':i+1,'overdue':0} for i in range(count)])
                    copy={'status':'available','copy_id':1,'title_id':title}
                    if allowed: service._issue_loan(c,2,9,copy)
                    else:
                        with self.assertRaisesRegex(service.DeskError,'limit'):
                            service._issue_loan(c,2,9,copy)

    def test_missing_barcode_rejected(self):
        c=MagicMock(); c.fetchone.return_value=None
        with self.assertRaisesRegex(service.DeskError,'barcode'): service._lock_copy(c,'missing')

    def test_normal_return_updates_loan_and_copy(self):
        c=MagicMock(); c.fetchone.return_value=None; c.rowcount=1
        service._close_loan(c,{'copy_id':1,'title_id':2,'status':'borrowed'})
        sql=' '.join(x.args[0] for x in c.execute.call_args_list)
        self.assertIn('returned_at = NOW()',sql)
        self.assertIn("status = 'available'",sql)

    def test_return_rejects_nonborrowed_copy(self):
        with self.assertRaisesRegex(service.DeskError,'not currently'):
            service._close_loan(MagicMock(),{'status':'available'})

    def test_return_with_waiting_reservation_allocates_copy(self):
        cursor = MagicMock()
        cursor.rowcount = 1
        copy = {"copy_id": 1, "title_id": 2, "status": "borrowed"}
        with patch.object(service, "allocate_available_copy", return_value=7) as allocate:
            reservation_id = service._close_loan(cursor, copy)
        self.assertEqual(reservation_id, 7)
        allocate.assert_called_once_with(cursor, 1)

    def test_return_without_open_loan_rejected(self):
        c=MagicMock(); c.fetchone.return_value=None; c.rowcount=0
        with self.assertRaisesRegex(service.DeskError,'No active loan'):
            service._close_loan(c,{'copy_id':1,'title_id':2,'status':'borrowed'})

    def test_borrow_commits_only_on_success(self):
        for failure in [False,True]:
            with self.subTest(failure=failure), patch.object(service,'connect') as connect, patch.object(service,'_lock_copy',return_value={'copy_id':1}), patch.object(service,'_issue_loan') as issue:
                connection=connect.return_value.__enter__.return_value
                if failure:
                    issue.side_effect=service.DeskError('blocked')
                    with self.assertRaises(service.DeskError): service.borrow(2,'KB-1',9)
                    connection.commit.assert_not_called()
                else:
                    service.borrow(2,'KB-1',9); connection.commit.assert_called_once()

    def test_self_borrow_locks_copy_and_commits_without_librarian(self):
        with patch.object(service, 'connect') as connect, patch.object(service, '_lock_copy', return_value={'copy_id': 1}) as lock, patch.object(service, '_issue_loan') as issue:
            connection = connect.return_value.__enter__.return_value
            cursor = connection.cursor.return_value.__enter__.return_value
            service.self_borrow(2, 'KB-1')
            lock.assert_called_once_with(cursor, 'KB-1')
            issue.assert_called_once_with(cursor, 2, None, {'copy_id': 1})
            connection.commit.assert_called_once()

    def test_self_borrow_failure_does_not_commit(self):
        with patch.object(service, 'connect') as connect, patch.object(service, '_lock_copy', side_effect=service.DeskError('unavailable')):
            with self.assertRaises(service.DeskError):
                service.self_borrow(2, 'KB-1')
            connect.return_value.__enter__.return_value.commit.assert_not_called()

    def test_reader_return_checks_owner_under_copy_lock(self):
        for owner in [None, {'reader_id': 999}, {'reader_id': 2}]:
            with self.subTest(owner=owner), patch.object(service, 'connect') as connect, patch.object(service, '_lock_copy', return_value={'copy_id': 1}), patch.object(service, '_close_loan') as close, patch.object(service, 'generate_overdue_fees'):
                connection = connect.return_value.__enter__.return_value
                cursor = connection.cursor.return_value.__enter__.return_value
                cursor.fetchone.return_value = owner
                if owner == {'reader_id': 2}:
                    service.return_copy('KB-1', reader_id=2)
                    close.assert_called_once()
                    connection.commit.assert_called_once()
                else:
                    with self.assertRaisesRegex(service.DeskError, 'own active loans'):
                        service.return_copy('KB-1', reader_id=2)
                    close.assert_not_called()
                    connection.commit.assert_not_called()
                self.assertIn('FOR UPDATE', cursor.execute.call_args.args[0])

    def test_reader_search_escapes_wildcards_and_scopes_loans(self):
        with patch.object(service, 'connect') as connect:
            cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchall.side_effect = [[], []]
            context = service.reader_desk_context(2, '100%_!')
            search, loans = cursor.execute.call_args_list
            self.assertEqual(search.args[1], ('100%_!', '%100!%!_!!%', '%100!%!_!!%', '100%_!'))
            self.assertEqual(loans.args[1], (2,))
            self.assertIn('l.reader_id = %s', loans.args[0])
            self.assertEqual(context['copies'], [])
