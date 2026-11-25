import unittest
from unittest.mock import patch, MagicMock
from werkzeug.security import generate_password_hash
from app import create_app
from catalogue.queries import CatalogueError

class RouteTests(unittest.TestCase):
    def setUp(self):
        self.app=create_app(); self.app.config.update(TESTING=True,SECRET_KEY='test-only')
        self.client=self.app.test_client()
        self.guard=patch('pymysql.connect',side_effect=AssertionError('Tests must not access shared database'))
        self.guard.start(); self.addCleanup(self.guard.stop)

    def login_session(self,role='reader'):
        with self.client.session_transaction() as s:
            s.update(user_id=2,username='test',role=role,reader_category='undergraduate' if role=='reader' else None)

    def test_anonymous_protected_routes_redirect_to_login(self):
        for path in ['/catalogue','/title/1','/my/loans','/my/fees','/my/reservations','/desk','/inventory']:
            with self.subTest(path=path):
                response=self.client.get(path)
                self.assertEqual(response.status_code,302); self.assertIn('/login',response.location)

    def test_reader_cannot_invoke_librarian_mutations(self):
        self.login_session()
        with patch('app.blueprints.desk.load_circulation') as load:
            for path in ['/desk/borrow','/desk/return','/desk/collect']:
                with self.subTest(path=path): self.assertEqual(self.client.post(path).status_code,302)
            load.assert_not_called()

    def test_login_success_and_role_destination(self):
        for role,destination in [('reader','/catalogue'),('librarian','/desk')]:
            with self.subTest(role=role), patch('app.blueprints.auth._find_user',return_value={'user_id':2,'username':'alice','password_hash':generate_password_hash('password'),'role':role,'reader_category':'undergraduate'}):
                self.client.post('/logout')
                response=self.client.post('/login',data={'username':'alice','password':'password'})
                self.assertEqual(response.status_code,303); self.assertTrue(response.location.endswith(destination))
                with self.client.session_transaction() as s: self.assertEqual(s['user_id'],2)

    def test_invalid_credentials_do_not_create_session(self):
        for user in [None,{'password_hash':generate_password_hash('correct')}]:
            with self.subTest(user_exists=user is not None), patch('app.blueprints.auth._find_user',return_value=user):
                self.assertEqual(self.client.post('/login',data={'username':'alice','password':'wrong'}).status_code,401)
                with self.client.session_transaction() as s: self.assertNotIn('user_id',s)

    def test_login_database_failure_returns_503(self):
        with patch('app.blueprints.auth._find_user',side_effect=RuntimeError('unavailable')):
            self.assertEqual(self.client.post('/login',data={'username':'alice'}).status_code,503)

    def test_logout_clears_authentication(self):
        self.login_session(); self.assertEqual(self.client.post('/logout').status_code,303)
        with self.client.session_transaction() as s: self.assertNotIn('user_id',s)
        self.assertIn('/login',self.client.get('/catalogue').location)

    def test_safe_next_rejects_external_redirects(self):
        from app.blueprints.auth import _safe_next
        for value in [None,'','https://example.com','//example.com']:
            with self.subTest(value=value): self.assertIsNone(_safe_next(value))
        self.assertEqual(_safe_next('/catalogue'),'/catalogue')

    def test_librarian_borrow_and_return_forward_normalized_input(self):
        self.login_session('librarian'); service=MagicMock()
        with patch('app.blueprints.desk.load_circulation',return_value={'service':service}):
            self.assertEqual(self.client.post('/desk/borrow',data={'reader_id':'2','barcode':' KB-1 '}).status_code,302)
            service.borrow.assert_called_once_with(2,'KB-1',2)
            self.assertEqual(self.client.post('/desk/return',data={'barcode':' KB-1 '}).status_code,302)
            service.return_copy.assert_called_once_with('KB-1')

    def test_borrow_error_is_presented_to_user(self):
        self.login_session('librarian'); service=MagicMock(); service.borrow.side_effect=ValueError('reader blocked')
        with patch('app.blueprints.desk.load_circulation',return_value={'service':service}):
            self.client.post('/desk/borrow',data={'reader_id':'2','barcode':'KB-1'})
        with self.client.session_transaction() as s: self.assertIn('reader blocked',[text for category,text in s['_flashes']])

    def test_missing_title_returns_404(self):
        self.login_session(); connection=MagicMock(); queries=MagicMock()
        queries.get_title.return_value=None; queries.get_copies_for_title.return_value=[]
        with patch('app.blueprints.catalogue.load_catalogue',return_value={'connect':connection,'queries':queries}):
            self.assertEqual(self.client.get('/title/999').status_code,404)

    def test_reader_forbidden_from_queue_administration(self):
        self.login_session(); self.assertEqual(self.client.get('/desk/reservations').status_code,403)

    def test_reservation_history_is_librarian_only(self):
        self.login_session()
        self.assertEqual(self.client.get('/desk/reservations/history').status_code,302)
        self.login_session('librarian')
        with patch('app.blueprints.reservations.load_reservations',return_value=None):
            self.assertEqual(self.client.get('/desk/reservations/history').status_code,200)


class CatalogueRouteTests(unittest.TestCase):
    def setUp(self):
        self.app=create_app(); self.app.config.update(TESTING=True,SECRET_KEY='test-only')
        self.client=self.app.test_client()
        self.guard=patch('pymysql.connect',side_effect=AssertionError('Tests must not access shared database'))
        self.guard.start(); self.addCleanup(self.guard.stop)

    def login_session(self,role='reader'):
        with self.client.session_transaction() as s:
            s.update(user_id=2,username='test',role=role,reader_category='undergraduate' if role=='reader' else None)

    def _catalogue(self, queries=None):
        return patch(
            'app.blueprints.catalogue.load_catalogue',
            return_value={'connect': MagicMock(), 'queries': queries or MagicMock()},
        )

    def _flashes(self):
        with self.client.session_transaction() as s:
            return ' '.join(text for _category, text in s.get('_flashes', []))

    def test_inventory_page_requires_librarian(self):
        self.assertEqual(self.client.get('/inventory').status_code,302)  # anonymous
        self.login_session('reader')
        self.assertEqual(self.client.get('/inventory').status_code,302)  # reader
        self.login_session('librarian')
        queries=MagicMock()
        queries.get_all_titles.return_value=[]
        queries.get_categories.return_value=[]
        with self._catalogue(queries):
            self.assertEqual(self.client.get('/inventory').status_code,200)

    def test_edit_title_page_renders_for_librarian(self):
        self.login_session('librarian')
        queries=MagicMock()
        queries.get_title.return_value={
            'title_id':1,'isbn':'9780132350884','title':'Clean Code',
            'author':'Robert C. Martin','category':'Computing',
            'description':'','has_digital_version':0,'cover_url':'',
        }
        queries.get_categories.return_value=[]
        with self._catalogue(queries):
            self.assertEqual(self.client.get('/titles/1/edit').status_code,200)

    def test_create_title_success(self):
        self.login_session('librarian')
        queries=MagicMock()
        with self._catalogue(queries):
            self.assertEqual(
                self.client.post('/titles',data={'isbn':'1','title':'T','author':'A','category':'C'}).status_code,
                302,
            )
        queries.create_title.assert_called_once()
        self.assertIn('Title added.', self._flashes())

    def test_create_title_validation_error_flashed(self):
        self.login_session('librarian')
        queries=MagicMock()
        queries.create_title.side_effect=CatalogueError('ISBN is required.')
        with self._catalogue(queries):
            self.assertEqual(
                self.client.post('/titles',data={'isbn':'','title':'T','author':'A','category':'C'}).status_code,
                302,
            )
        self.assertIn('ISBN is required.', self._flashes())

    def test_create_copy_success(self):
        self.login_session('librarian')
        queries=MagicMock()
        queries.find_title_id_by_name.return_value=1
        with self._catalogue(queries):
            self.assertEqual(
                self.client.post('/copies',data={'title':'Clean Code','barcode':'KB-1','status':'available'}).status_code,
                302,
            )
        queries.find_title_id_by_name.assert_called_once()
        queries.create_copy.assert_called_once()
        self.assertIn('Copy registered.', self._flashes())

    def test_create_copy_unknown_title_preserves_input(self):
        self.login_session('librarian')
        queries=MagicMock()
        queries.find_title_id_by_name.return_value=None
        queries.get_all_titles.return_value=[]
        queries.get_categories.return_value=[]
        with self._catalogue(queries):
            response=self.client.post(
                '/copies',
                data={'title':'No Such Book','barcode':'KB-123','status':'available','location':''},
            )
        self.assertEqual(response.status_code,200)
        html=response.get_data(as_text=True)
        self.assertIn('That title does not exist.', html)
        self.assertIn('No Such Book', html)
        self.assertIn('KB-123', html)
        queries.create_copy.assert_not_called()

    def test_update_copy_status_rejects_borrowed(self):
        self.login_session('librarian')
        queries=MagicMock()
        queries.update_copy_status.side_effect=CatalogueError(
            'This copy is currently on loan or reserved and cannot be changed here.'
        )
        with self._catalogue(queries):
            self.assertEqual(
                self.client.post('/copies/2/status',data={'title_id':'1','status':'lost','location':''}).status_code,
                302,
            )
        self.assertIn('on loan or reserved', self._flashes())

    def test_reader_cannot_invoke_catalogue_mutations(self):
        self.login_session('reader')
        queries=MagicMock()
        with self._catalogue(queries):
            for path in ['/titles','/titles/1','/copies','/copies/1/status']:
                with self.subTest(path=path):
                    self.assertEqual(self.client.post(path).status_code,302)
        queries.create_title.assert_not_called()
        queries.update_title.assert_not_called()
        queries.create_copy.assert_not_called()
        queries.update_copy_status.assert_not_called()
