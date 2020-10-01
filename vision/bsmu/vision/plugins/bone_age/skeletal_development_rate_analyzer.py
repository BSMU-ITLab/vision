import math
from enum import Enum

from bsmu.vision_core.equations import PolynomialInterval


class SkeletalDevelopmentRate(Enum):
    UNKNOWN = 1
    PREMATURE = 2
    NORMAL = 3
    SLOW = 4


# See the skeletal-development-rate.xlsx
# To analyze the polynomial coefficients was used https://arachnoid.com/polysolve/ site
class SkeletalDevelopmentRateAnalyzer:
    MALE_AVERAGE_BONE_AGE_POLYNOMIAL_INTERVAL = PolynomialInterval([
        1.9601518746019124e+000, 9.5955434792749217e-001, 2.4597241569502149e-004, 5.4254446590035720e-007,
        -1.9566105816636058e-009, 2.2001996490752735e-012, -1.2954750184389476e-015, 4.5338315436311031e-019,
        -9.7814491751118083e-023, 1.2783121989414781e-026, -9.2872050935116074e-031, 2.8796406133652001e-035,
    ], 91.31, 6209.12)

    MALE_AVERAGE_BONE_AGE_SIGMA_POLYNOMIAL_INTERVAL = PolynomialInterval([
        5.6091785650024789e+001, -6.6467190655033925e-001, 4.1053500498319101e-003, -9.0343824257306146e-006,
        1.0494786591569399e-008, -7.1250278232119307e-012, 2.9485841943334061e-015, -7.3012428582647804e-019,
        9.0231983010487826e-023, 2.1085027223121054e-027, -2.5944592825244799e-030, 4.0268923167932070e-034,
        -2.8583978314624709e-038, 8.1386140430310350e-043,
    ], 91.31, 6209.12)

    FEMALE_AVERAGE_BONE_AGE_POLYNOMIAL_INTERVAL = PolynomialInterval([
        2.7511509390756380e+001, 6.4538354307682966e-001, 1.0861217709336596e-003, 2.1417065652946575e-007,
        -5.2275803206685262e-009, 9.0662221594663157e-012, -7.5060273330081332e-015, 3.5835048810139450e-018,
        -1.0529629649885595e-021, 1.9769492418722839e-025, -2.6036265658578534e-029, 2.9906098057951388e-033,
        -2.4861280972221896e-037, -2.3429985160007063e-041, 1.0473441734940426e-044, -1.1847880261493611e-048,
        4.6914293358687177e-053,
    ], 91.31, 5843.88)

    FEMALE_AVERAGE_BONE_AGE_SIGMA_POLYNOMIAL_INTERVAL = PolynomialInterval([
        6.6474886977294801e+001, -7.6765993401528498e-001, 4.2422597731470325e-003, -8.4801011460518275e-006,
        8.5725077889549438e-009, -4.3375155981238011e-012, 6.9419905026226893e-016, 3.6818870419027735e-019,
        -2.4109858797819948e-022, 6.3232262586839576e-026, -8.9638244809987302e-030, 6.7441330376857084e-034,
        -2.1180329929610896e-038,
    ], 91.31, 5843.88)

    @staticmethod
    def gender_average_bone_age_polynomial_intervals():
        return {True: SkeletalDevelopmentRateAnalyzer.MALE_AVERAGE_BONE_AGE_POLYNOMIAL_INTERVAL,
                False: SkeletalDevelopmentRateAnalyzer.FEMALE_AVERAGE_BONE_AGE_POLYNOMIAL_INTERVAL}

    @staticmethod
    def gender_average_bone_age_sigma_polynomial_intervals():
        return {True: SkeletalDevelopmentRateAnalyzer.MALE_AVERAGE_BONE_AGE_SIGMA_POLYNOMIAL_INTERVAL,
                False: SkeletalDevelopmentRateAnalyzer.FEMALE_AVERAGE_BONE_AGE_SIGMA_POLYNOMIAL_INTERVAL}

    @staticmethod
    def analyze_skeletal_development_rate(male: bool, age_in_image: float, bone_age: float) -> SkeletalDevelopmentRate:
        average_bone_age = SkeletalDevelopmentRateAnalyzer.analyze_average_bone_age(male, age_in_image)
        average_bone_age_sigma = SkeletalDevelopmentRateAnalyzer.analyze_average_bone_age_sigma(male, age_in_image)
        if math.isnan(average_bone_age) or math.isnan(average_bone_age_sigma):
            return SkeletalDevelopmentRate.UNKNOWN

        # print(f'age: {age_in_image}\taverage_bone_age: {average_bone_age}\tsigma: {average_bone_age_sigma}\n'
        #       f'min: {average_bone_age - 2 * average_bone_age_sigma}\tmax: {average_bone_age + 2 * average_bone_age_sigma}\tcur_bone_age: {bone_age}')

        bone_age_delta = bone_age - average_bone_age
        if abs(bone_age_delta) <= 2 * average_bone_age_sigma:
            return SkeletalDevelopmentRate.NORMAL
        elif bone_age_delta > 0:
            return SkeletalDevelopmentRate.PREMATURE
        else:
            return SkeletalDevelopmentRate.SLOW

    @staticmethod
    def analyze_average_bone_age(male: bool, age_in_image) -> float:
        return SkeletalDevelopmentRateAnalyzer.gender_average_bone_age_polynomial_intervals()[male].calculate(
            age_in_image)

    @staticmethod
    def analyze_average_bone_age_sigma(male: bool, age_in_image) -> float:
        return SkeletalDevelopmentRateAnalyzer.gender_average_bone_age_sigma_polynomial_intervals()[male].calculate(
            age_in_image)
