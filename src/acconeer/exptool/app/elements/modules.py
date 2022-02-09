import acconeer.exptool.a111.algo.breathing._meta as breathing_meta
import acconeer.exptool.a111.algo.button_press._meta as button_press_meta
import acconeer.exptool.a111.algo.button_press_sparse._meta as button_press_sparse_meta
import acconeer.exptool.a111.algo.distance_detector._meta as distance_detector_meta
import acconeer.exptool.a111.algo.envelope._meta as envelope_meta
import acconeer.exptool.a111.algo.iq._meta as iq_meta
import acconeer.exptool.a111.algo.obstacle_detection._meta as obstacle_detection_meta
import acconeer.exptool.a111.algo.parking._meta as parking_meta
import acconeer.exptool.a111.algo.phase_tracking._meta as phase_tracking_meta
import acconeer.exptool.a111.algo.power_bins._meta as power_bins_meta
import acconeer.exptool.a111.algo.presence_detection_sparse._meta as presence_detection_sparse_meta
import acconeer.exptool.a111.algo.sleep_breathing._meta as sleep_breathing_meta
import acconeer.exptool.a111.algo.sparse._meta as sparse_meta
import acconeer.exptool.a111.algo.sparse_fft._meta as sparse_fft_meta
import acconeer.exptool.a111.algo.sparse_inter_fft._meta as sparse_inter_fft_meta
import acconeer.exptool.a111.algo.sparse_speed._meta as sparse_speed_meta


MODULE_INFOS = [
    envelope_meta.module_info,
    iq_meta.module_info,
    power_bins_meta.module_info,
    sparse_meta.module_info,
    presence_detection_sparse_meta.module_info,
    sparse_fft_meta.module_info,
    sparse_inter_fft_meta.module_info,
    sparse_speed_meta.module_info,
    breathing_meta.module_info,
    phase_tracking_meta.module_info,
    sleep_breathing_meta.module_info,
    obstacle_detection_meta.module_info,
    button_press_meta.module_info,
    button_press_sparse_meta.module_info,
    distance_detector_meta.module_info,
    parking_meta.module_info,
]

MODULE_KEY_TO_MODULE_INFO_MAP = {mi.key: mi for mi in MODULE_INFOS}
MODULE_LABEL_TO_MODULE_INFO_MAP = {mi.label: mi for mi in MODULE_INFOS}
