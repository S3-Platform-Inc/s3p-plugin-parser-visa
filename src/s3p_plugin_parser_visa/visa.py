import datetime
import time

from s3p_sdk.exceptions.parser import S3PPluginParserFinish, S3PPluginParserOutOfRestrictionException
from s3p_sdk.plugin.payloads.parsers import S3PParserBase
from s3p_sdk.types import S3PRefer, S3PDocument, S3PPlugin, S3PPluginRestrictions
from s3p_sdk.types.plugin_restrictions import FROM_DATE
from selenium.common import NoSuchElementException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

import dateutil.parser


class VISA(S3PParserBase):
    """
    A Parser payload that uses S3P Parser base class.
    """
    HOST = 'https://usa.visa.com'

    def __init__(self, refer: S3PRefer, plugin: S3PPlugin, restrictions: S3PPluginRestrictions, web_driver: WebDriver):
        super().__init__(refer, plugin, restrictions)

        # Тут должны быть инициализированы свойства, характерные для этого парсера. Например: WebDriver
        self._driver = web_driver
        self._wait = WebDriverWait(self._driver, timeout=20)

    def _parse(self):
        """
        Метод, занимающийся парсингом. Он добавляет в _content_document документы, которые получилось обработать
        :return:
        :rtype:
        """
        # HOST - это главная ссылка на источник, по которому будет "бегать" парсер
        self.logger.debug(F"Parser enter to {self.HOST}")

        # ========================================
        # Тут должен находится блок кода, отвечающий за парсинг конкретного источника
        # -
        self._driver.set_page_load_timeout(40)

        blog_link = 'https://usa.visa.com/visa-everywhere/blog.html'

        try:
            self._parsing_visa_press_release()
        except S3PPluginParserOutOfRestrictionException as e:
            if e.restriction == FROM_DATE:
                self.logger.debug(f'Document is out of date range `{self._restriction.from_date}`')
        try:
            self._parsing_visa_archive()
        except S3PPluginParserOutOfRestrictionException as e:
            if e.restriction == FROM_DATE:
                self.logger.debug(f'Document is out of date range `{self._restriction.from_date}`')
                raise S3PPluginParserFinish(self._plugin, f'Document is out of date range `{self._restriction.from_date}`', e)
        # ---
        # ========================================

    def _parsing_visa_press_release(self):
        press_release_link = 'https://usa.visa.com/about-visa/newsroom/press-releases-listing.html#2a'
        self.logger.debug(f'Start parse press-releases from url: {press_release_link}')

        self._initial_access_source(press_release_link, 4)

        tabs = self._driver.find_elements(By.CLASS_NAME, 'tab-pane')

        links = []

        for tab in tabs:
            articles = tab.find_elements(By.TAG_NAME, "a")
            # dates = tab.find_elements(By.TAG_NAME, "p")

            for article in articles:
                link = article.get_attribute('href')
                if link:
                    links.append(link)

        for link in links:
            self._parse_press_release_page(link)

    def _parse_press_release_page(self, url: str):
        self.logger.debug(f'Start parse press-release from url: {url}')

        try:
            self._initial_access_source(url, 3)
            title = self._driver.find_element(By.XPATH, '//*[@id="response1"]/div[1]/h1').text
            date = self._driver.find_element(By.XPATH, '//*[@id="response1"]/div[1]/p').text
            pub_date = dateutil.parser.parse(date)
            text = self._driver.find_element(By.CLASS_NAME, 'press-release-body').text

            document = S3PDocument(None, title, None, text, url, None, None, pub_date, datetime.datetime.now())
            self._find(document)
            # self._content_document.append(document)
        except S3PPluginParserFinish as correct_error:
            raise correct_error
        except S3PPluginParserOutOfRestrictionException as e:
            # Document is out of date range, continue to next material.
            # You can also use a restriction exception to skip irrelevant materials later on.
            raise e
        except Exception as e:
            self.logger.error(e)

    def _parsing_visa_archive(self):
        archive_link = ('https://usa.visa.com/partner-with-us/visa-consulting-analytics/leverage-economic-and-business'
                        '-insights/archives.html')

        self.logger.debug(f'Start parse press-releases from url: {archive_link}')
        self._initial_access_source(archive_link, 5)

        links = []

        tabs = self._driver.find_elements(By.CLASS_NAME, 'vs-accordion-content')
        for tab in tabs:
            sections = tab.find_elements(By.CLASS_NAME, 'section')

            for section in sections:
                article = section.find_element(By.TAG_NAME, 'a')
                try:
                    date = section.find_element(By.TAG_NAME, 'span')
                    pub_date = dateutil.parser.parse(date.get_attribute('innerText'))
                except Exception as e:
                    self.logger.error(e)
                    continue
                link = article.get_attribute('href')

                # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                # Вот это нужно поменять, если мы захотим скачивать файлы тоже.
                if link and link.endswith('.html'):
                    links.append((link, pub_date))
        for index, (link, pub_date) in enumerate(links):
            self._parse_archive_page(link, pub_date)

    def _parse_archive_page(self, url: str, pub_date: datetime.datetime):
        self.logger.debug(f'Start parse archive from url: {url}')

        try:
            self._initial_access_source(url, 3)
            title = self._driver.find_element(By.XPATH, '//*[@id="skipTo"]/div[1]/div/div[1]/div[2]/div/h1').text
            text = self._driver.find_element(By.CLASS_NAME, 'vs-page-section').text

            document = S3PDocument(None, title, None, text, url, None, None, pub_date, datetime.datetime.now())
            self._find(document)
            # self._content_document.append(document)
        except S3PPluginParserFinish as correct_error:
            raise correct_error
        except S3PPluginParserOutOfRestrictionException as e:
            # Document is out of date range, continue to next material.
            # You can also use a restriction exception to skip irrelevant materials later on.
            raise e
        except Exception as e:
            self.logger.error(e)

    def _initial_access_source(self, url: str, delay: int = 2):
        self._driver.get(url)
        self.logger.debug('Entered on web page ' + url)
        time.sleep(delay)
        self._agree_cookie_pass()

    def _agree_cookie_pass(self):
        """
        Метод прожимает кнопку agree на модальном окне
        """
        cookies = (
            (By.CSS_SELECTOR, '#CookieReportsBanner > div.wscrBannerContent > div.wscrBannerContentInner > a.wscrOk'),
            (By.XPATH, '//*[@id="onetrust-accept-btn-handler"]')
        )

        for cookie in cookies:
            try:
                cookie_button = self._driver.find_element(cookie[0], cookie[1])
                if WebDriverWait(self._driver, 5).until(ec.element_to_be_clickable(cookie_button)):
                    cookie_button.click()
                    self.logger.debug(F"Parser pass cookie modal on page: {self._driver.current_url}")
                    break
            except NoSuchElementException as e:
                self.logger.debug(f'modal agree not found on page: {self._driver.current_url}')

