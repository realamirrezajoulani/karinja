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

