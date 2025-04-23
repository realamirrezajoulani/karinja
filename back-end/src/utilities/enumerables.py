from enum import Enum


class LogicalOperator(str, Enum):
    AND = "and"
    OR = "or"
    NOT = "not"

class UserRole(str, Enum):
    FULL_ADMIN = "full_admin"
    ADMIN = "admin"
    EMPLOYER = "employer"
    JOB_SEEKER = "job_seeker"


class UserAccountStatus(str, Enum):
    ACTIVE = "فعال"
    INACTIVE = "غیر فعال"
    SUSPENDED = "به تعلیق در آمده"


class EmploymentStatusJobSeekerResume(str, Enum):
    JOB_SEEKER = "کارجو"
    LOOKING_FOR_A_BETTER_JOB = "به دنبال شغل بهتر"
    EMPLOYED = "شاغل"


class IranProvinces(str, Enum):
    AZARBAYJAN_SHARQI = "آذربایجان شرقی"
    AZARBAYJAN_GHARBI = "آذربایجان غربی"
    ARDABIL = "اردبیل"
    ESFAHAN = "اصفهان"
    ALBORZ = "البرز"
    ILAM = "ایلام"
    BUSHEHR = "بوشهر"
    TEHRAN = "تهران"
    CHAHARAMAHAL_VA_BAKHTIYARI = "چهارمحال و بختیاری"
    KHORASAN_JONUBI = "خراسان جنوبی"
    KHORASAN_REZAVI = "خراسان رضوی"
    KHORASAN_SHOMALI = "خراسان شمالی"
    KHUZESTAN = "خوزستان"
    ZANJAN = "زنجان"
    SEMNAN = "سمنان"
    SISTAN_VA_BALUCHESTAN = "سیستان و بلوچستان"
    FARS = "فارس"
    QAZVIN = "قزوین"
    QOM = "قم"
    KURDISTAN = "کردستان"
    KERMAN = "کرمان"
    KERMANSHAH = "کرمانشاه"
    KOHGILUUYEH_VA_BOYER_AHMAD = "کهگیلویه و بویراحمد"
    GOLASTAN = "گلستان"
    GILAN = "گیلان"
    LORESTAN = "لرستان"
    MAZANDARAN = "مازندران"
    MARKAZI = "مرکزی"
    HORMOZGAN = "هرمزگان"
    HAMEDAN = "همدان"
    YAZD = "یزد"


class JobSeekerMaritalStatus(str, Enum):
    UNMARRIED = "مجرد"
    MARRIED = "متاهل"


class JobSeekerGender(str, Enum):
    MAN = "مرد",
    WOMAN = "زن"
    OTHER = "سایر"


class JobSeekerMilitaryServiceStatus(str, Enum):
    COMPLETED = "انجام شده"
    IN_PROGRESS = "در حال انجام"
    DEFERRED = "معوق"
    EXEMPT = "معاف از خدمت"
    ACADEMIC_EXEMPT = "معافیت تحصیلی"
    MEDICAL_EXEMPT = "معافیت پزشکی"


class JobSeekerProficiencyLevel(str, Enum):
    BEGINNER = "مبتدی"
    INTERMEDIATE = "متوسط"
    PROFESSIONAL = "حرفه‌ای"
    LEARNING = "در حال یادگیری"


class JobSeekerCertificateVerificationStatus(str, Enum):
    VERIFIED = "تایید شده"
    PENDING = "در انتظار تایید"
    UNVERIFIED = "تایید نشده"


class JobSeekerEducationDegree(str, Enum):
    PRIMARY_SCHOOL = "دبستان"
    MIDDLE_SCHOOL = "متوسطه اول"
    HIGH_SCHOOL = "دبیرستان"
    DIPLOMA = "دیپلم"
    ASSOCIATE_DEGREE = "کاردانی"
    BACHELORS_DEGREE = "کارشناسی"
    MASTERS_DEGREE = "کارشناسی ارشد"
    DOCTORATE_DEGREE = "دکتری"
    OTHER = "سایر"


class EmployerCompanyIndustry(str, Enum):
    AGRICULTURE = "کشاورزی"
    ANIMAL_HUSBANDRY = "دامداری"
    FISHERIES = "شیلات"
    MINING = "معادن"
    FORESTRY = "جنگلداری"
    MANUFACTURING = "صنایع تولیدی"
    CONSTRUCTION = "صنایع ساخت‌وساز"
    CHEMICAL_INDUSTRIES = "صنایع شیمیایی"
    ENERGY_INDUSTRIES = "صنایع انرژی"
    COMMERCIAL_SERVICES = "خدمات تجاری"
    FINANCIAL_SERVICES = "خدمات مالی"
    HEALTH_SERVICES = "خدمات بهداشتی"
    EDUCATIONAL_SERVICES = "خدمات آموزشی"
    COMMUNICATION_SERVICES = "خدمات ارتباطی"
    TOURISM_AND_LEISURE = "گردشگری و تفریحی"
    INFORMATION_TECHNOLOGY = "فناوری اطلاعات"
    RESEARCH_AND_DEVELOPMENT = "تحقیق و توسعه"
    CONSULTING_AND_PROFESSIONAL_SERVICES = "مشاوره و خدمات حرفه‌ای"
    ADVANCED_EDUCATION_AND_TRAINING = "آموزش‌های پیشرفته و تخصصی"
    EXECUTIVE_MANAGEMENT_SERVICES = "خدمات مدیریت عالی"
    HIGHER_EDUCATION_AND_SPECIALIZED_TRAINING = "آموزش‌های عالی و تخصصی"
    SPECIALIZED_MEDICAL_CARE = "مراقبت‌های پزشکی تخصصی"
    ART_AND_CULTURE = "هنر و فرهنگ"
    ADVANCED_RESEARCH_AND_INNOVATION = "تحقیقات و نوآوری‌های پیشرفته"
    OTHER = "سایر"


class EmployerCompanyOwnershipType(str, Enum):
    PRIVATE = "خصوصی"
    PUBLIC = "عمومی"
    COOPERATIVE = "تعاونی"
    MIXED = "مختلط"
    STATE = "دولتی"
    PRIVATE_SECTOR = "بخش خصوصی"
    PUBLIC_PRIVATE_PARTNERSHIP = "مشارکت عمومی-خصوصی"
    NON_PROFIT = "غیرانتفاعی"
    CORPORATE = "شرکتی"


class EmployerCompanyEmployeeCount(str, Enum):
    SMALL = "1-50"
    MEDIUM = "51-200"
    LARGE = "201-1000"
    ENTERPRISE = "1001+"


class ImageType(str, Enum):
    Profile = "پروفایل"
    BACKGROUND = "پس‌زمینه"
    OTHER = "دیگر"


class JobPostingEmploymentType(str, Enum):
    FULL_TIME = "تمام‌وقت"
    PART_TIME = "پاره‌وقت"
    CONTRACTOR = "قراردادی"
    TEMPORARY = "موقت"
    VOLUNTEER = "داوطلبانه"
    INTERN = "کارآموز"
    OTHER = "سایر"


class JobPostingSalaryUnit(str, Enum):
    HOUR = "ساعتی"
    DAY = "روزانه"
    WEEK = "هفتگی"
    MONTH = "ماهانه"
    YEAR = "سالانه"
    OTHER = "سایر"


class JobPostingJobCategory(str, Enum):
    MANAGEMENT = "مدیریتی"
    TECHNICAL = "فنی"
    SERVICE = "خدماتی"
    ADMINISTRATIVE = "اداری"
    SALES = "فروش"
    SUPPORT = "پشتیبانی"
    PRODUCTION = "تولیدی"
    EDUCATION = "آموزشی"
    HEALTHCARE = "بهداشتی"
    OTHER = "سایر"


class JobPostingStatus(str, Enum):
    PENDING_APPROVAL = "در انتظار تایید"
    PUBLISHED = "منتشر شده"
    PAUSED = "متوقف شده"
    EXPIRED = "منقضی شده"
    CANCELLED = "لغو شده"
    ARCHIVED = "بایگانی شده"


class JobApplicationStatus(str, Enum):
    SUBMITTED = "ارسال شده"
    UNDER_REVIEW = "در حال بررسی"
    INTERVIEW_SCHEDULED = "مصاحبه برنامه‌ریزی شده"
    INTERVIEWED = "مصاحبه انجام شده"
    REJECTED = "رد شده"
    WITHDRAWN = "انصراف داده شده"
    ARCHIVED = "بایگانی شده"


class NotificationType(str, Enum):
    INFORMATIVE = "اطلاع‌رسانی"
    URGENT = "فوری"
    REMINDER = "یادآوری"
    ALERT = "هشدار"
    PROMOTIONAL = "تبلیغاتی"
    SYSTEM = "سیستمی"


class ActivityLogType(str, Enum):
    GET_USER = "مشاهده کاربر"
    GET_ALL_USERS = "مشاهده تمامی کاربران"
    POST_USER = "ایجاد کاربر"
    UPDATE_USER = "ویرایش کاربر"
    DELETE_USER = "حذف کاربر"
    
    GET_EMPLOYER_COMPANY = "مشاهده شرکت کارفرما"
    GET_ALL_EMPLOYER_COMPANY = "مشاهده تمامی شرکت‌های کارفرما"
    POST_EMPLOYER_COMPANY = "ایجاد شرکت کارفرما"
    UPDATE_EMPLOYER_COMPANY = "ویرایش شرکت کارفرما"
    DELETE_EMPLOYER_COMPANY = "حذف شرکت کارفرما"
    
    GET_JOB_APPLICATION = "مشاهده درخواست شغلی"
    GET_ALL_JOB_APPLICATION = "مشاهده تمامی درخواست‌های شغلی"
    POST_JOB_APPLICATION = "ایجاد درخواست شغلی"
    UPDATE_JOB_APPLICATION = "ویرایش درخواست شغلی"
    DELETE_JOB_APPLICATION = "حذف درخواست شغلی"
    
    GET_JOB_POSTING = "مشاهده آگهی شغلی"
    GET_ALL_JOB_POSTING = "مشاهده تمامی آگهی‌های شغلی"
    POST_JOB_POSTING = "ایجاد آگهی شغلی"
    UPDATE_JOB_POSTING = "ویرایش آگهی شغلی"
    DELETE_JOB_POSTING = "حذف آگهی شغلی"
    
    GET_JOB_SEEKER_EDUCATION = "مشاهده تحصیلات جویای کار"
    GET_ALL_JOB_SEEKER_EDUCATION = "مشاهده تمامی تحصیلات جویای کار"
    POST_JOB_SEEKER_EDUCATION = "اضافه کردن تحصیلات جویای کار"
    UPDATE_JOB_SEEKER_EDUCATION = "ویرایش تحصیلات جویای کار"
    DELETE_JOB_SEEKER_EDUCATION = "حذف تحصیلات جویای کار"
    
    GET_JOB_SEEKER_PERSONAL_INFORMATION = "مشاهده شخصی جویای کار"
    GET_ALL_JOB_SEEKER_PERSONAL_INFORMATION = "مشاهده تمامی شخصی جویای کار"
    POST_JOB_SEEKER_PERSONAL_INFORMATION = "اضافه کردن شخصی جویای کار"
    UPDATE_JOB_SEEKER_PERSONAL_INFORMATION = "ویرایش شخصی جویای کار"
    DELETE_JOB_SEEKER_PERSONAL_INFORMATION = "حذف شخصی جویای کار"
    
    GET_JOB_SEEKER_RESUME = "مشاهده رزومه جویای کار"
    GET_ALL_JOB_SEEKER_RESUME = "مشاهده تمامی رزومه‌های جویای کار"
    POST_JOB_SEEKER_RESUME = "اضافه کردن رزومه جویای کار"
    UPDATE_JOB_SEEKER_RESUME = "ویرایش رزومه جویای کار"
    DELETE_JOB_SEEKER_RESUME = "حذف رزومه جویای کار"
    
    GET_JOB_SEEKER_SKILL = "مشاهده مهارت‌های جویای کار"
    GET_ALL_JOB_SEEKER_SKILL = "مشاهده تمامی مهارت‌های جویای کار"
    POST_JOB_SEEKER_SKILL = "اضافه کردن مهارت‌های جویای کار"
    UPDATE_JOB_SEEKER_SKILL = "ویرایش مهارت‌های جویای کار"
    DELETE_JOB_SEEKER_SKILL = "حذف مهارت‌های جویای کار"
    
    GET_JOB_SEEKER_WORK_EXPERIENCE = "مشاهده تجربه کاری جویای کار"
    GET_ALL_JOB_SEEKER_WORK_EXPERIENCE = "مشاهده تمامی تجربه‌های کاری جویای کار"
    POST_JOB_SEEKER_WORK_EXPERIENCE = "اضافه کردن تجربه کاری جویای کار"
    UPDATE_JOB_SEEKER_WORK_EXPERIENCE = "ویرایش تجربه کاری جویای کار"
    DELETE_JOB_SEEKER_WORK_EXPERIENCE = "حذف تجربه کاری جویای کار"
    
    GET_SAVED_JOB = "مشاهده شغل‌های ذخیره شده"
    GET_ALL_SAVED_JOB = "مشاهده تمامی شغل‌های ذخیره شده"
    POST_SAVED_JOB = "ذخیره شغل"
    DELETE_SAVED_JOB = "حذف شغل ذخیره شده"
    
    GET_NOTIFICATION = "مشاهده اعلان‌ها"
    GET_ALL_NOTIFICATION = "مشاهده تمامی اعلان‌ها"
    POST_NOTIFICATION = "ایجاد اعلان"
    UPDATE_NOTIFICATION = "ویرایش اعلان"
    DELETE_NOTIFICATION = "حذف اعلان"
    
    GET_IMAGE = "مشاهده تصویر"
    GET_ALL_IMAGE = "مشاهده تمامی تصاویر"
    UPDATE_IMAGE = "ویرایش تصویر"
    POST_IMAGE = "بارگذاری تصویر"
    DELETE_IMAGE = "حذف تصویر"

    SYSTEM_ERROR = "خطای سیستمی"
    LOGIN = "ورود"
    SIGNUP = "ثبت نام"

    OTHER = "سایر"
