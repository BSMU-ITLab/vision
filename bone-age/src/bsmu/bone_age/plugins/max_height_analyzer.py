from __future__ import annotations

from typing import Callable

from bsmu.bone_age.plugins.skeletal_development_rate_analyzer import SkeletalDevelopmentRate
from bsmu.vision.core.equations import polynomial


# See the max-height.xlsx
# To analyze the polynomial coefficients was used https://arachnoid.com/polysolve/ site
class MaxHeightAnalyzer:
    MALE_PREMATURE_BONE_GROWTH_FACTOR_POLYNOMIAL_COEFFS = [
        5.2844060362323171e+003, -1.0661861096867558e+001, 9.4256945040339535e-003, -4.7198093963127405e-006,
        1.4662112825682316e-009, -2.8945107769443715e-013, 3.5452812683701658e-017, -2.4611015314729219e-021,
        7.4043874845177370e-026,
    ]

    MALE_NORMAL_BONE_GROWTH_FACTOR_POLYNOMIAL_COEFFS = [
        -9.3563263370955901e+003, 1.6398179838259580e+001, -1.1216060395050478e-002, 3.5044690864016520e-006,
        -2.8233357162745612e-010, -1.1450282071615700e-013, 2.2663770922694529e-017, 4.3061097318494215e-021,
        -2.0856328364062524e-024, 3.1510287701720420e-028, -2.2303735330746286e-032, 6.2705541834193816e-037,
    ]

    MALE_SLOW_BONE_GROWTH_FACTOR_POLYNOMIAL_COEFFS = [
        3.4411400742436608e+003, -7.6350593937607574e+000, 7.2931855693045894e-003, -3.8203105338301699e-006,
        1.1863162051844338e-009, -2.1825034250542001e-013, 2.2008669266264437e-017, -9.3784979132931955e-022,
    ]

    FEMALE_PREMATURE_BONE_GROWTH_FACTOR_POLYNOMIAL_COEFFS = [
        3.0115865536171605e+004, -4.9669765615027529e+001, 3.0850813816880915e-002, -7.8160327546727290e-006,
        -4.9776325522948417e-012, 3.9054506982865333e-013, -7.4450596209930203e-017, 9.8106630792529319e-021,
        -1.5309232481315911e-024, -2.3651554589623904e-028, 1.2315247399404932e-031, -9.4742703342692364e-036,
        -1.1062047918264180e-039, 3.6024442489724852e-043, -2.7956774632441069e-047, -8.6803255309891201e-051,
        4.4306664797132093e-055, 5.1886915214384223e-059, 6.1672932927644152e-062, -2.5826024409396129e-066,
        -1.2102311865291804e-069, -1.0483398340704939e-073, 2.5570367949869516e-077, -1.8617482769347864e-081,
        4.5021770810989976e-085, 6.5795027777286478e-089, -2.0049042230981812e-092, 1.1336194034699093e-096,
        -1.1555377970531961e-100, -9.9150762150525878e-105, 7.6882121626567739e-108, -8.3590177194860305e-112,
        2.6917935083079335e-116,
    ]

    FEMALE_NORMAL_BONE_GROWTH_FACTOR_POLYNOMIAL_COEFFS = [
        -4.3409096562095965e+003, 8.2543215537413701e+000, -5.2590756073246994e-003, 5.2871007386097440e-007,
        9.2792257950628707e-010, -4.5898298381143356e-013, 6.9353307571334625e-017, 4.5063317983621949e-021,
        -1.8891549536936386e-024, -1.5320504106062590e-029, 3.4812408176372713e-032, -9.6400721664339893e-036,
        2.0700067576472224e-039, 1.2425441124314962e-043, -4.0555359793018601e-047, -1.1172322873518206e-050,
        1.4384127059604765e-054, 7.4130646098993442e-059, 2.7773723417689728e-062, -4.9269482285661918e-066,
        -1.1132406418137504e-070, -4.5800807768031154e-074, 9.4950363786159910e-078, -9.3839341976494068e-082,
        2.0213406117557087e-085, 1.7786016403282436e-089, -4.6458228591887145e-093, -3.4811189380647699e-097,
        1.0773196994345895e-100, -1.5034146104597450e-104, 1.6888918319358494e-108, -7.7074980732945240e-113,
    ]

    FEMALE_SLOW_BONE_GROWTH_FACTOR_POLYNOMIAL_COEFFS = [
        -8.6686079027225678e+003, 1.8515998926685747e+001, -1.5901271700457579e-002, 6.9083552129397716e-006,
        -1.4888200271775418e-009, 9.8841154874012690e-014, 1.7975408569727662e-017, -4.9491420818533180e-021,
        7.5515872855914177e-025, 9.3856519087278689e-029, -7.0802629128525263e-032, 8.3602506724198538e-036,
        3.8502019678865447e-041, -1.4024323488029012e-043, 5.8875014336929789e-047, -6.6960975709691103e-051,
        4.7352009218805158e-055, -1.4263304820482013e-058, -2.4371801880447037e-062, 2.1649918500869114e-066,
        1.0900585315693204e-069, 3.8092061327153083e-074, 1.4713431371406287e-077, -9.5927414917786445e-081,
        5.2239167407804712e-085, -8.6099983762103859e-089, 2.6700068152694081e-092, -1.3812441498812828e-096,
        5.6773462896421982e-101, -2.7861592748785739e-104, 7.9161659686676861e-108, -1.4031037679823132e-111,
        8.4835724081386758e-116,
    ]

    @staticmethod
    def max_height_factor_functions_for_premature_bone_growth():
        return {True: MaxHeightAnalyzer.male_premature_bone_growth_factor_in_range,
                False: MaxHeightAnalyzer.female_premature_bone_growth_factor_in_range}

    @staticmethod
    def max_height_factor_functions_for_normal_bone_growth():
        return {True: MaxHeightAnalyzer.male_normal_bone_growth_factor_in_range,
                False: MaxHeightAnalyzer.female_normal_bone_growth_factor_in_range}

    @staticmethod
    def max_height_factor_functions_for_slow_bone_growth():
        return {True: MaxHeightAnalyzer.male_slow_bone_growth_factor_in_range,
                False: MaxHeightAnalyzer.female_slow_bone_growth_factor_in_range}

    @staticmethod
    def max_height_factor_functions_for_bone_growth():
        return {SkeletalDevelopmentRate.PREMATURE: MaxHeightAnalyzer.max_height_factor_functions_for_premature_bone_growth(),
                SkeletalDevelopmentRate.NORMAL: MaxHeightAnalyzer.max_height_factor_functions_for_normal_bone_growth(),
                SkeletalDevelopmentRate.SLOW: MaxHeightAnalyzer.max_height_factor_functions_for_slow_bone_growth(),
                }

    @staticmethod
    def male_premature_bone_growth_factor(bone_age: float) -> float:
        return polynomial(bone_age, MaxHeightAnalyzer.MALE_PREMATURE_BONE_GROWTH_FACTOR_POLYNOMIAL_COEFFS)

    @staticmethod
    def male_normal_bone_growth_factor(bone_age: float) -> float:
        return polynomial(bone_age, MaxHeightAnalyzer.MALE_NORMAL_BONE_GROWTH_FACTOR_POLYNOMIAL_COEFFS)

    @staticmethod
    def male_slow_bone_growth_factor(bone_age: float) -> float:
        return polynomial(bone_age, MaxHeightAnalyzer.MALE_SLOW_BONE_GROWTH_FACTOR_POLYNOMIAL_COEFFS)

    @staticmethod
    def female_premature_bone_growth_factor(bone_age: float) -> float:
        return polynomial(bone_age, MaxHeightAnalyzer.FEMALE_PREMATURE_BONE_GROWTH_FACTOR_POLYNOMIAL_COEFFS)

    @staticmethod
    def female_normal_bone_growth_factor(bone_age: float) -> float:
        return polynomial(bone_age, MaxHeightAnalyzer.FEMALE_NORMAL_BONE_GROWTH_FACTOR_POLYNOMIAL_COEFFS)

    @staticmethod
    def female_slow_bone_growth_factor(bone_age: float) -> float:
        return polynomial(bone_age, MaxHeightAnalyzer.FEMALE_SLOW_BONE_GROWTH_FACTOR_POLYNOMIAL_COEFFS)

    @staticmethod
    def bone_growth_factor_in_range(bone_age: float, bone_age_min: float, bone_age_max: float,
                                    bone_growth_factor_function: Callable) -> float:
        return bone_growth_factor_function(bone_age) if bone_age_min <= bone_age <= bone_age_max else float('nan')

    @staticmethod
    def male_premature_bone_growth_factor_in_range(bone_age: float) -> float:
        return MaxHeightAnalyzer.bone_growth_factor_in_range(
            bone_age, 2557, 6209, MaxHeightAnalyzer.male_premature_bone_growth_factor)

    @staticmethod
    def male_normal_bone_growth_factor_in_range(bone_age: float) -> float:
        return MaxHeightAnalyzer.bone_growth_factor_in_range(
            bone_age, 2557, 6757, MaxHeightAnalyzer.male_normal_bone_growth_factor)

    @staticmethod
    def male_slow_bone_growth_factor_in_range(bone_age: float) -> float:
        return MaxHeightAnalyzer.bone_growth_factor_in_range(
            bone_age, 2191, 4748, MaxHeightAnalyzer.male_slow_bone_growth_factor)

    @staticmethod
    def female_premature_bone_growth_factor_in_range(bone_age: float) -> float:
        return MaxHeightAnalyzer.bone_growth_factor_in_range(
            bone_age, 2557, 6392, MaxHeightAnalyzer.female_premature_bone_growth_factor)

    @staticmethod
    def female_normal_bone_growth_factor_in_range(bone_age: float) -> float:
        return MaxHeightAnalyzer.bone_growth_factor_in_range(
            bone_age, 2191, 6574, MaxHeightAnalyzer.female_normal_bone_growth_factor)

    @staticmethod
    def female_slow_bone_growth_factor_in_range(bone_age: float) -> float:
        return MaxHeightAnalyzer.bone_growth_factor_in_range(
            bone_age, 2191, 6209, MaxHeightAnalyzer.female_slow_bone_growth_factor)
