from enum import Enum


class UserRole(str, Enum):
    FULL_ADMIN = "ادمین کامل"
    ADMIN = "ادمین"
    EMPLOYER = "کارفرما"
    JOB_SEEKER = "کارجو"


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
