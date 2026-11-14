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
                service._issue_loan(c,2,{'copy_id':1,'title_id':1,'status':'available'})
                insert=[x for x in c.execute.call_args_list if 'INSERT INTO loan' in x.args[0]]
                self.assertEqual(insert[0].args[1],(2,1,service.DEMO_LIBRARIAN,days))
                self.assertIn("status = 'borrowed'",c.execute.call_args.args[0])

    def test_invalid_reader_rejected(self):
        c=MagicMock(); c.fetchone.return_value=None
        with self.assertRaisesRegex(service.DeskError,'valid reader'):
            service._issue_loan(c,999,{'status':'available'})

    def test_nonavailable_statuses_rejected(self):
        for status in ['borrowed','reserved','damaged','lost','under_repair']:
            with self.subTest(status=status):
                with self.assertRaisesRegex(service.DeskError,'unavailable'):
                    service._issue_loan(self.cursor(),2,{'status':status})

    def test_overdue_reader_rejected(self):
        c=self.cursor(loans=[{'title_id':3,'overdue':1}])
        with self.assertRaisesRegex(service.DeskError,'overdue'):
            service._issue_loan(c,2,{'status':'available'})

    def test_unpaid_fee_rejected(self):
        with self.assertRaisesRegex(service.DeskError,'unpaid'):
            service._issue_loan(self.cursor(fee={'exists':1}),2,{'status':'available'})

    def test_distinct_title_limit_boundaries(self):
        for category, limit in [('undergraduate',5),('postgraduate',10),('teaching_staff',10)]:
            for count,title,allowed in [(limit-1,999,True),(limit,999,False),(limit,1,True)]:
                with self.subTest(category=category,count=count,title=title):
                    c=self.cursor(category,[{'title_id':i+1,'overdue':0} for i in range(count)])
                    copy={'status':'available','copy_id':1,'title_id':title}
                    if allowed: service._issue_loan(c,2,copy)
                    else:
                        with self.assertRaisesRegex(service.DeskError,'limit'):
                            service._issue_loan(c,2,copy)

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

    def test_return_with_waiting_reservation_is_currently_rejected(self):
        c=MagicMock(); c.fetchone.return_value={'exists':1}
        with self.assertRaisesRegex(service.DeskError,'reservation processing'):
            service._close_loan(c,{'copy_id':1,'title_id':2,'status':'borrowed'})

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
                    with self.assertRaises(service.DeskError): service.borrow(2,'KB-1')
                    connection.commit.assert_not_called()
                else:
                    service.borrow(2,'KB-1'); connection.commit.assert_called_once()
