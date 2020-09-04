from __future__ import annotations

from typing import List, Callable, Optional


def regression(x: float, coeffs: List[float]):
    x_degree = 1
    result = 0
    for coeff in coeffs:
        result += coeff * x_degree
        x_degree *= x
    return result


class MaxHeightAnalyzer:
    FEMALE_SLOW_BONE_GROWTH_FACTOR_REGRESSION_COEFFS = [
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
    def male_premature_bone_growth_factor(bone_age: float) -> float:
        return + 2.50113274E-19 * pow(bone_age, 6) \
               - 6.66720200E-15 * pow(bone_age, 5) \
               + 7.19815031E-11 * pow(bone_age, 4) \
               - 4.02823790E-07 * pow(bone_age, 3) \
               + 1.23390613E-03 * pow(bone_age, 2) \
               - 1.95789341E+00 * bone_age \
               + 1.32221016E+03

    @staticmethod
    def male_normal_bone_growth_factor(bone_age: float) -> float:
        return - 9.276905164E-23 * pow(bone_age, 7) \
               + 3.236206163E-18 * pow(bone_age, 6) \
               - 4.722921311E-14 * pow(bone_age, 5) \
               + 3.732712195E-10 * pow(bone_age, 4) \
               - 1.723840612E-06 * pow(bone_age, 3) \
               + 4.650210758E-03 * pow(bone_age, 2) \
               - 6.777851909E+00 * bone_age \
               + 4.183814392E+03

    @staticmethod
    def male_slow_bone_growth_factor(bone_age: float) -> float:
        return - 7.88803944E-19 * pow(bone_age, 6) \
               + 1.66497865E-14 * pow(bone_age, 5) \
               - 1.43117573E-10 * pow(bone_age, 4) \
               + 6.41569034E-07 * pow(bone_age, 3) \
               - 1.58484072E-03 * pow(bone_age, 2) \
               + 2.05990341E+00 * bone_age \
               - 1.04054970E+03

    @staticmethod
    def female_premature_bone_growth_factor(bone_age: float) -> float:
        return + 7.385819011E-20 * pow(bone_age, 6) \
               - 1.876044660E-15 * pow(bone_age, 5) \
               + 1.955514425E-11 * pow(bone_age, 4) \
               - 1.076849728E-07 * pow(bone_age, 3) \
               + 3.311507425E-04 * pow(bone_age, 2) \
               - 5.280993082E-01 * bone_age \
               + 4.053146801E+02

    @staticmethod
    def female_normal_bone_growth_factor(bone_age: float) -> float:
        return - 1.7336626326896891e+004 * pow(bone_age, 0) + 3.4487522982262021e+001 * pow(bone_age, 1) \
               - 2.6992906121429572e-002 * pow(bone_age, 2) + 1.0521445559625643e-005 * pow(bone_age, 3) \
               - 2.4700951328203732e-009 * pow(bone_age, 4) + 7.6520578273415177e-013 * pow(bone_age, 5) \
               - 3.3437169121647562e-016 * pow(bone_age, 6) + 8.0826390225753212e-020 * pow(bone_age, 7) \
               - 5.1636152249149347e-024 * pow(bone_age, 8) - 6.8732029651583897e-028 * pow(bone_age, 9) \
               - 8.3041449125649256e-032 * pow(bone_age, 10) + 3.2926189458780523e-035 * pow(bone_age, 11) \
               + 3.1929648352220792e-039 * pow(bone_age, 12) - 7.0755726529149096e-043 * pow(bone_age, 13) \
               - 6.5258178958479517e-047 * pow(bone_age, 14) + 1.3417035155014420e-050 * pow(bone_age, 15) \
               - 8.3504548221191948e-055 * pow(bone_age, 16) - 7.4739635052259305e-059 * pow(bone_age, 17) \
               + 1.4209175491218753e-062 * pow(bone_age, 18) - 1.6851839856129141e-066 * pow(bone_age, 19) \
               + 1.4236731119162944e-069 * pow(bone_age, 20) + 2.0256370824364538e-074 * pow(bone_age, 21) \
               - 3.9200230084282213e-077 * pow(bone_age, 22) + 2.3674089795491615e-081 * pow(bone_age, 23) \
               - 6.1094966196995399e-085 * pow(bone_age, 24) - 1.0012505979071848e-090 * pow(bone_age, 25) \
               + 1.4600808740556591e-092 * pow(bone_age, 26) - 7.1362522865812172e-098 * pow(bone_age, 27) \
               - 5.6634170792177066e-101 * pow(bone_age, 28) + 7.4495479959974126e-104 * pow(bone_age, 29) \
               - 9.4508707106549118e-108 * pow(bone_age, 30) - 1.4795821871468861e-111 * pow(bone_age, 31) \
               + 3.4812070811653912e-115 * pow(bone_age, 32) - 5.2965048479012451e-119 * pow(bone_age, 33) \
               + 5.7042011845007940e-124 * pow(bone_age, 34) + 1.3348000078776241e-126 * pow(bone_age, 35) \
               - 8.3981356844100094e-131 * pow(bone_age, 36) - 1.0057522908894416e-134 * pow(bone_age, 37) \
               + 8.1117666094257750e-139 * pow(bone_age, 38)

    @staticmethod
    def female_slow_bone_growth_factor(bone_age: float) -> float:
        return regression(bone_age, MaxHeightAnalyzer.FEMALE_SLOW_BONE_GROWTH_FACTOR_REGRESSION_COEFFS)

    @staticmethod
    def bone_growth_factor_in_range(bone_age: float, bone_age_min: float, bone_age_max: float,
                                    bone_growth_factor_function: Callable) -> Optional[float]:
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
