import subprocess
import tempfile
from typing import List

import cv2
from PyQt6.QtGui import QPainterPath, QPixmap
from svgpathtools import svg2paths
from svgpathtools.path import CubicBezier, Line

# from beziers.path import BezierPath
# from beziers.point import Point
# from beziers.segment import Segment
# from beziers.utils.curvefitter import CurveFit
# from beziers.path.representations.Segment import SegmentRepresentation


class BezierTracing:
    def __init__(self, image_path):
        self.image_path = image_path
        self._opencv_original_image = None
        self._opencv_image = None
        self._opencv_contours = None
        self._potrace_path = None
        self._simoncozens_beziers = None
        self._simoncozens_path = None
        self._qt_pixmap = None

    @property
    def opencv_original_image(self):
        if self._opencv_original_image is None:
            self._opencv_original_image = cv2.imread(self.image_path)
        return self._opencv_original_image

    @property
    def opencv_image(self):
        if self._opencv_image is None:
            self._opencv_image = self._preprocess_opencv_image()
        return self._opencv_image

    def _preprocess_opencv_image(self):
        gray_img = cv2.cvtColor(self.opencv_original_image, cv2.COLOR_BGR2GRAY)
        _, threshold_img = cv2.threshold(gray_img, 120, 255, cv2.THRESH_BINARY_INV)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (1, 1))
        dilated_img = cv2.dilate(threshold_img, kernel)
        final_img = cv2.bitwise_not(dilated_img)
        return final_img

    @property
    def qt_pixmap(self):
        if self._qt_pixmap is None:
            # cv_rgb = cv2.cvtColor(self.opencv_original_image, cv2.COLOR_BGR2RGB)
            # h, w = cv_rgb.shape[:2]
            # qt_img = QImage(cv_rgb.flatten(), w, h, QImage.Format.Format_RGB888)
            # self._qt_pixmap = QPixmap.fromImage(qt_img)
            self._qt_pixmap = QPixmap(self.image_path)
        return self._qt_pixmap

    @property
    def opencv_contours(self):
        if self._opencv_contours is None:
            self._opencv_contours, _ = cv2.findContours(self.opencv_image, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        return self._opencv_contours

    @property
    def potrace_path(self):
        if self._potrace_path is None:
            self._potrace_path = self.run_potrace()
        return self._potrace_path

    def run_potrace(self):
        retval, buf = cv2.imencode(".bmp", self.opencv_image)
        if retval == False:
            raise ValueError("Failed to convert into BMP binary data")
        binbmp = buf.tobytes()
        args = ["potrace", "-", "-o-", "-b", "svg"]
        p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
        stdout, stderr = p.communicate(input=binbmp)
        if len(stderr) != 0:
            raise RuntimeError("Potrace threw error:\n" + stderr.decode("utf-8"))
        svg = stdout.decode("utf-8")
        qt_path_list = self.svg2qt_path_list(svg)
        qt_path_list = self._get_filled_path_list(qt_path_list)
        return qt_path_list

    def svg2qt_path_list(self, svg: str) -> List[QPainterPath]:
        svg_path = tempfile.NamedTemporaryFile().name
        with open(svg_path, mode="w", encoding="utf-8") as f:
            f.write(svg)
        pathes, _, svg_attributes = svg2paths(svg_path, return_svg_attributes=True)
        height = float(svg_attributes["height"][:-2])
        qt_path_list = []
        end_point = None
        for path in pathes:
            qt_path = QPainterPath()
            for segment in path:
                qt_points = [(bpoint.real, bpoint.imag) for bpoint in segment.bpoints()]
                start_point = qt_points[0]
                if start_point != end_point:
                    if not qt_path.isEmpty():
                        qt_path.closeSubpath()
                        qt_path_list.append(qt_path)
                        qt_path = QPainterPath()
                    qt_path.moveTo(qt_points[0][0] / 10, -qt_points[0][1] / 10 + height)
                # else:
                if isinstance(segment, Line):
                    qt_path.lineTo(qt_points[1][0] / 10, -qt_points[1][1] / 10 + height)
                elif isinstance(segment, CubicBezier):
                    qt_path.cubicTo(
                        qt_points[1][0] / 10,
                        -qt_points[1][1] / 10 + height,
                        qt_points[2][0] / 10,
                        -qt_points[2][1] / 10 + height,
                        qt_points[3][0] / 10,
                        -qt_points[3][1] / 10 + height,
                    )
                else:
                    exit()
                end_point = qt_points[-1]
            else:
                qt_path.closeSubpath()
                qt_path_list.append(qt_path)
        return qt_path_list

    def _get_filled_path_list(self, path_list: List[QPainterPath]):
        filled_path_list = []
        sorted_path_list = sorted(path_list, key=lambda x: x.boundingRect().x())
        while sorted_path_list:
            outer_path = sorted_path_list.pop(0)
            hole_path_list = []
            inner_path_list = [path for path in sorted_path_list if outer_path.contains(path)]
            while inner_path_list:
                hole_path = inner_path_list.pop(0)
                for inner_path in inner_path_list[:]:
                    if hole_path.contains(inner_path):
                        inner_path_list.remove(inner_path)
                hole_path_list.append(hole_path)
                sorted_path_list.remove(hole_path)
            filled_path = QPainterPath(outer_path)
            for hole_path in hole_path_list:
                filled_path.addPath(hole_path)
            filled_path_list.append(filled_path)
        return filled_path_list

    # @property
    # def simoncozens_path(self):
    #     if self._simoncozens_path is None:
    #         self._simoncozens_path = self.run_simoncozens_bezier()
    #     return self._simoncozens_path

    # def simoncozens_beziers2qt_path(self,simoncozens_beziers:List[BezierPath]):
    #     svgs = []
    #     for bezier in simoncozens_beziers:
    #         try:
    #             svg = bezier.asSVGPath()
    #             svgs.append(svg)
    #         except:
    #             pass
    #     path_svg = " ".join([f'<path  d="{svg}"/>' for svg in svgs])
    #     svg = f"<svg >{path_svg}</svg>"
    #     qt_path = self.svg2qt_path_list(svg)
    #     return qt_path

    # def run_simoncozens_bezier(self):
    #     self._simoncozens_beziers = []
    #     for contour in self.opencv_contours:
    #         points = [Point(val[0][0], val[0][1]) for val in contour.tolist()]
    #         segs = CurveFit.fitCurve(points, error=1, cornerTolerance=20, maxSegments=1000)
    #         bezier = BezierPath()
    #         bezier.closed = True
    #         bezier.activeRepresentation = SegmentRepresentation(bezier, segs)
    #         self._simoncozens_beziers.append(bezier)
    #     return self.simoncozens_beziers2qt_path(self._simoncozens_beziers)
