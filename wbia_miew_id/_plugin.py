# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
from wbia.control import controller_inject
from wbia.constants import ANNOTATION_TABLE, UNKNOWN
from wbia.constants import CONTAINERIZED, PRODUCTION  # NOQA
import numpy as np
import utool as ut
import vtool as vt
import wbia
from wbia import dtool as dt
import os
import torch
from torch.cuda.amp import autocast, GradScaler
import torchvision.transforms as transforms  # noqa: E402
from scipy.spatial import distance_matrix
import pandas as pd

import tqdm

from wbia_miew_id.helpers import get_config, read_json
from wbia_miew_id.models import get_model
from wbia_miew_id.datasets import PluginDataset, get_test_transforms
from wbia_miew_id.metrics import pred_light, compute_distance_matrix, eval_onevsall
from wbia_miew_id.visualization import draw_one, draw_batch


(print, rrr, profile) = ut.inject2(__name__)

_, register_ibs_method = controller_inject.make_ibs_register_decorator(__name__)

register_api = controller_inject.get_wbia_flask_api(__name__)
register_route = controller_inject.get_wbia_flask_route(__name__)

register_preproc_image = controller_inject.register_preprocs['image']
register_preproc_annot = controller_inject.register_preprocs['annot']


DEMOS = {
    'whale_beluga': '',
}

REMOVED_CONFIGS ={
    'leopard': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.leopard.yaml',
    'wilddog': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_4cats.yaml',
    'leopard': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_4cats.yaml',
    'snow_leopard': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_4cats.yaml',
}

CONFIGS = {
    'whale_beluga': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'delphinapterus_leucas': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'tursiops_truncatus': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'dolphin_whitesided+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'white_shark+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'carcharodon_carcharias': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'spinner_dolphin': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'stenella_longirostris': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'sotalia_guianensis': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'short_fin_pilot_whale+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'globicephala_melas': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'pilot_whale+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'globicephala_macrorhynchus': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'globicephala_melas': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'short_fin_pilot_whale+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'hyperoodon_ampullatus': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'whale_humpback+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'whale_fluke': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'megaptera_novaeangliae': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'lagenodelphis_hosei': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'cougar+head': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_face.yaml',
    'lion+head': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_face.yaml',
    'lioness+head': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_face.yaml',
    'lion_general+head': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_face.yaml',
    'panthera_leo': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_face.yaml',
    'dolphin_spotted+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'dolphin_spotted': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'stenella_frontalis': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'stenella_attenuata': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'whale_falsekiller': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'pseudorca_crassidens': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'dolphin_rissos+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'grampus_griseus': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'phocoena_phocoena': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'harbour_porpoise+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'balaenoptera_acutorostrata+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'whale_minke+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'whale_pilot+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'ziphiidae_sp': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'dolphin_bottlenose+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'whale_fin+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'whale_fin': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'whale_gervais+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'whale_gervais': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'whale_beaked+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'whale_beaked': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'balaenoptera_brydei': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'balaenoptera_borealis': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'whale_orca+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'dolphin_roughtoothed+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'whale_orca': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'whale_grey': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'whale_grey+fluke': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'whale_humpback+fluke': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'whale_sperm+fluke': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'physeter_macrocephalus': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'right_whale+head_aerial':'https://cthulhu.dyn.wildme.io/public/models/miew_id.rightwhale.yaml',
    'right_whale+fluke':'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.yaml',
    'eubalaena_glacialis':'https://cthulhu.dyn.wildme.io/public/models/miew_id.rightwhale.yaml',
    'right_whale+head_lateral':'https://cthulhu.dyn.wildme.io/public/models/miew_id.rightwhale.yaml',
    'panthera_pardus': 'https://cthulhu.dyn.wildme.io/public/models/miew_id_ms_9cats.yaml',
    'hyaena': 'https://cthulhu.dyn.wildme.io/public/models/miew_id_ms_9cats.yaml',
    'crocuta_crocuta': 'https://cthulhu.dyn.wildme.io/public/models/miew_id_ms_9cats.yaml',
    'hyaena_brown': 'https://cthulhu.dyn.wildme.io/public/models/miew_id_ms_9cats.yaml',
    'hyaena_brunnea': 'https://cthulhu.dyn.wildme.io/public/models/miew_id_ms_9cats.yaml',
    'wild_dog_dark': 'https://cthulhu.dyn.wildme.io/public/models/miew_id_ms_9cats.yaml',
    'wild_dog': 'https://cthulhu.dyn.wildme.io/public/models/miew_id_ms_9cats.yaml',
    'wild_dog_puppy': 'https://cthulhu.dyn.wildme.io/public/models/miew_id_ms_9cats.yaml',
    'wild_dog_tan': 'https://cthulhu.dyn.wildme.io/public/models/miew_id_ms_9cats.yaml',
    'wild_dog_general': 'https://cthulhu.dyn.wildme.io/public/models/miew_id_ms_9cats.yaml',
    'wild_dog_standard': 'https://cthulhu.dyn.wildme.io/public/models/miew_id_ms_9cats.yaml',
    'wild_dog_ambiguous': 'https://cthulhu.dyn.wildme.io/public/models/miew_id_ms_9cats.yaml',
    'wild_dog+tail_double_black_white': 'https://cthulhu.dyn.wildme.io/public/models/miew_id_ms_9cats.yaml',
    'lycaon_pictus': 'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'wilddog':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'snow_leopard':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'panthera_uncia':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'lynx_lynx':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'cheetah':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'acinonyx_jubatus':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'hyena':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'lynx_pardinus':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'leopard':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'jaguar':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'panthera_onca':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'amur_tiger':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'panthera_tigris':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'ocelot':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'leopardus_pardalis':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'tiger_cat':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'leopardus_guttulus':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'serval':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'lion':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'lioness':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'lion_general':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'leptailurus_serval':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.yaml',
    'giraffe_whole' : 'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.yaml',
    'giraffe_reticulated' : 'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.yaml',
    'giraffe_masai' : 'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.yaml',
    'giraffe_tippelskirchi' : 'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.yaml',
    'giraffe_tippelskirchi_thornicrofti' : 'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.yaml',
    'giraffa_giraffa_angolensis' : 'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.yaml',
    'giraffa_giraffa_giraffa' : 'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.yaml',
    'giraffa_giraffa' : 'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.yaml',
    'giraffa_camelopardalis_camelopardalis' : 'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.yaml',
    'giraffa_camelopardalis_peralta' : 'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.yaml',
    'giraffa_camelopardalis' : 'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.yaml',
    'giraffa_reticulata' : 'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.yaml',
    'chelonia_mydas' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.yaml',
    'eretmochelys_imbricata' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.yaml',
    'turtle_asian' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.yaml',
    'turtle_green' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.yaml',
    'turtle_green+head' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.yaml',
    'turtle_hawksbill' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.yaml',
    'turtle_hawksbill+head' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.yaml',
    'turtle_oliveridley' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.yaml',
    'turtle_oliveridley+head' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.yaml',
    'turtle_sea' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.yaml',
    'turtle_sea+head' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.yaml',
    'turtle_loggerhead' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.yaml',
    'turtle_loggerhead+head' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.yaml',
    }



# This section attempts to load the model configuration from a JSON file.
#  - FileNotFoundError: Raised if the file is not found.
#  - json.JSONDecodeError: Raised if the file content is not valid JSON.
# If no errors occur, the MODELS variable is loaded successfully and a message is printed.

try:
  with open('/v_config/miewid/model_config.json', 'r') as config_file:
    CONFIGS = json.load(config_file)
except FileNotFoundError:
  print("Error: File not found. Please check the file path /v_config/miewid/model_config.json ")
except json.JSONDecodeError:
  print("Error: Invalid JSON format. Please check the file content /v_config/miewid/model_config.json.")
else:
  print("CONFIGS file loaded successfully.")



REMOVED_MODELS = {
    'leopard': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.leopard.bin',
    'leopard': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_4cats.bin',
    'wilddog': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_4cats.bin',
    'snow_leopard': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_4cats.bin',
    'wilddog': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_4cats.bin',
    'lion+head': 'https://cthulhu.dyn.wildme.io/public/models/miewid_lion_head_v0.bin',
    'lioness+head': 'https://cthulhu.dyn.wildme.io/public/models/miewid_lion_head_v0.bin',
    'lion_general+head': 'https://cthulhu.dyn.wildme.io/public/models/miewid_lion_head_v0.bin',
    'panthera_leo': 'https://cthulhu.dyn.wildme.io/public/models/miewid_lion_head_v0.bin',
    'cougar+head': 'https://cthulhu.dyn.wildme.io/public/models/miewid_lion_head_v0.bin',
}

MODELS = {
    'whale_beluga': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'delphinapterus_leucas': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'tursiops_truncatus': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'dolphin_whitesided+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'white_shark+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'carcharodon_carcharias': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'spinner_dolphin': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'stenella_longirostris': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'sotalia_guianensis': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'short_fin_pilot_whale+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'globicephala_melas': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'pilot_whale+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'globicephala_macrorhynchus': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'globicephala_melas': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'short_fin_pilot_whale+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'hyperoodon_ampullatus': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'whale_humpback+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'whale_fluke': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'megaptera_novaeangliae': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'lagenodelphis_hosei': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'lion+head': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_face.bin',
    'lioness+head': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_face.bin',
    'lion_general+head': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_face.bin',
    'panthera_leo': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_face.bin',
    'cougar+head': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_face.bin',
    'dolphin_spotted+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'dolphin_spotted': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'stenella_frontalis': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'stenella_attenuata': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'whale_falsekiller': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'pseudorca_crassidens': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'dolphin_rissos+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'grampus_griseus': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'phocoena_phocoena': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'harbour_porpoise+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'balaenoptera_acutorostrata+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'whale_minke+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'dolphin_bottlenose+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'whale_fin+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'whale_fin': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'whale_beaked+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'whale_beaked': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'whale_gervais+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'whale_gervais': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'whale_pilot+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'ziphiidae_sp': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'balaenoptera_brydei': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'balaenoptera_borealis': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',   
    'whale_orca+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'dolphin_roughtoothed+fin_dorsal': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'whale_orca': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'whale_grey': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'whale_grey+fluke': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'whale_humpback+fluke': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'whale_sperm+fluke': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'physeter_macrocephalus': 'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'right_whale+head_aerial':'https://cthulhu.dyn.wildme.io/public/models/miew_id.rightwhale.bin',
    'right_whale+fluke':'https://cthulhu.dyn.wildme.io/public/models/miew_id.ms_flukebook.bin',
    'eubalaena_glacialis':'https://cthulhu.dyn.wildme.io/public/models/miew_id.rightwhale.bin',
    'right_whale+head_lateral':'https://cthulhu.dyn.wildme.io/public/models/miew_id.rightwhale.bin',
    'panthera_pardus': 'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'hyaena': 'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'crocuta_crocuta': 'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'hyaena_brown': 'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'hyaena_brunnea': 'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'wild_dog_dark': 'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'wild_dog': 'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'wild_dog_puppy': 'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'wild_dog_tan': 'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'wild_dog_general': 'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'wild_dog_standard': 'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'wild_dog_ambiguous': 'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'wild_dog+tail_double_black_white': 'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'lycaon_pictus': 'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'wilddog':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'snow_leopard':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'panthera_uncia':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'lynx_lynx':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'cheetah':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'acinonyx_jubatus':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'hyena':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'lynx_pardinus':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'leopard':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'jaguar':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'panthera_onca':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'amur_tiger':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'panthera_tigris':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'ocelot':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'leopardus_pardalis':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'tiger_cat':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'leopardus_guttulus':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'serval':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'lion':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'lioness':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'lion_general':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'leptailurus_serval':'https://wildbookiarepository.azureedge.net/models/miew_id_ms_9cats.bin',
    'giraffe_whole':'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.bin',
    'giraffe_reticulated':'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.bin',
    'giraffe_masai':'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.bin',
    'giraffe_tippelskirchi':'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.bin',
    'giraffe_tippelskirchi_thornicrofti':'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.bin',
    'giraffa_giraffa_angolensis':'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.bin',
    'giraffa_giraffa_giraffa':'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.bin',
    'giraffa_giraffa':'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.bin',
    'giraffa_camelopardalis_camelopardalis':'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.bin',
    'giraffa_camelopardalis':'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.bin',
    'giraffa_camelopardalis_peralta':'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.bin',
    'giraffa_reticulata':'https://wildbookiarepository.azureedge.net/models/miew_id.giraffe.bin',
    'chelonia_mydas' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.bin',
    'eretmochelys_imbricata' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.bin',
    'turtle_asian' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.bin',
    'turtle_green' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.bin',
    'turtle_green+head' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.bin',
    'turtle_hawksbill' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.bin',
    'turtle_hawksbill+head' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.bin',
    'turtle_oliveridley' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.bin',
    'turtle_oliveridley+head' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.bin',
    'turtle_sea' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.bin',
    'turtle_sea+head' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.bin',
    'turtle_loggerhead' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.bin',
    'turtle_loggerhead+head' : 'https://wildbookiarepository.azureedge.net/models/miew_id.iot_v2.bin',
}


# This section attempts to load the model bin configuration from a JSON file.
#  - FileNotFoundError: Raised if the file is not found.
#  - json.JSONDecodeError: Raised if the file content is not valid JSON.
# If no errors occur, the MODELS variable is loaded successfully and a message is printed.
try:
  with open('/v_config/miewid/model_bin_config.json', 'r') as config_file:
    MODELS = json.load(config_file)
except FileNotFoundError:
  print("Error: File not found. Please check the file path /v_config/miewid/model_bin_config.json ")
except json.JSONDecodeError:
  print("Error: Invalid JSON format. Please check the file content /v_config/miewid/model_bin_config.json.")
else:
  print("MODELS bin config file loaded successfully.")



GLOBAL_EMBEDDING_CACHE = {}


@register_ibs_method
def miew_id_embedding(ibs, aid_list, config=None, use_depc=True):
    r"""
    Generate embeddings for MiewID
    Args:
        ibs (IBEISController): IBEIS / WBIA controller object
        aid_list  (int): annot ids specifying the input
        use_depc (bool): use dependency cache
    CommandLine:
        python -m wbia_miew_id._plugin miew_id_embedding
    Example:
        >>> # ENABLE_DOCTEST
        >>> import wbia_miew_id
        >>> from wbia_miew_id._plugin import DEMOS, CONFIGS, MODELS
        >>> species = 'rhincodon_typus'
        >>> test_ibs = wbia_miew_id._plugin.wbia_miew_id_test_ibs(DEMOS[species], species, 'test2021')
        >>> aid_list = test_ibs.get_valid_aids(species=species)
        >>> rank1 = test_ibs.evaluate_distmat(aid_list, CONFIGS[species], use_depc=False)
        >>> expected_rank1 = 0.81366
        >>> assert abs(rank1 - expected_rank1) < 1e-2

    Example:
        >>> # ENABLE_DOCTEST
        >>> import wbia_miew_id
        >>> from wbia_miew_id._plugin import DEMOS, CONFIGS, MODELS
        >>> species = 'whale_grey'
        >>> test_ibs = wbia_miew_id._plugin.wbia_miew_id_test_ibs(DEMOS[species], species, 'test2021')
        >>> aid_list = test_ibs.get_valid_aids(species=species)
        >>> rank1 = test_ibs.evaluate_distmat(aid_list, CONFIGS[species], use_depc=False)
        >>> expected_rank1 = 0.69505
        >>> assert abs(rank1 - expected_rank1) < 1e-2

    Example:
        >>> # ENABLE_DOCTEST
        >>> import wbia_miew_id
        >>> from wbia_miew_id._plugin import DEMOS, CONFIGS, MODELS
        >>> species = 'horse_wild'
        >>> test_ibs = wbia_miew_id._plugin.wbia_miew_id_test_ibs(DEMOS[species], species, 'test2021')
        >>> aid_list = test_ibs.get_valid_aids(species=species)
        >>> rank1 = test_ibs.evaluate_distmat(aid_list, CONFIGS[species], use_depc=False)
        >>> expected_rank1 = 0.32773
        >>> assert abs(rank1 - expected_rank1) < 1e-2

    """
    global GLOBAL_EMBEDDING_CACHE

    dirty_aids = []
    for aid in aid_list:
        if aid not in GLOBAL_EMBEDDING_CACHE:
            dirty_aids.append(aid)

    if len(dirty_aids) > 0:
        print('Computing %d non-cached embeddings' % (len(dirty_aids), ))
        if use_depc:
            config_map = {'config_path': config}
            dirty_embeddings = ibs.depc_annot.get(
                'MiewIdEmbedding', dirty_aids, 'embedding', config_map
            )
        else:
            dirty_embeddings = miew_id_compute_embedding(ibs, dirty_aids, config)

        for dirty_aid, dirty_embedding in zip(dirty_aids, dirty_embeddings):
            GLOBAL_EMBEDDING_CACHE[dirty_aid] = dirty_embedding

    embeddings = ut.take(GLOBAL_EMBEDDING_CACHE, aid_list)

    return embeddings


class MiewIdEmbeddingConfig(dt.Config):  # NOQA
    _param_info_list = [
        ut.ParamInfo('config_path', default=None),
    ]


@register_preproc_annot(
    tablename='MiewIdEmbedding',
    parents=[ANNOTATION_TABLE],
    colnames=['embedding'],
    coltypes=[np.ndarray],
    configclass=MiewIdEmbeddingConfig,
    fname='miew_id',
    chunksize=128,
)
@register_ibs_method
def miew_id_embedding_depc(depc, aid_list, config=None):
    ibs = depc.controller
    embs = miew_id_compute_embedding(ibs, aid_list, config=config['config_path'])
    for aid, emb in zip(aid_list, embs):
        yield (np.array(emb),)


@register_ibs_method
def miew_id_compute_embedding(ibs, aid_list, config=None, multithread=False):
    # Get species from the first annotation
    species = ibs.get_annot_species_texts(aid_list[0])

    # Load config
    if config is None:
        config = CONFIGS[species]
    config = _load_config(config)

    # Load model
    model = _load_model(config, MODELS[species])

    # Initialize the gradient scaler
    scaler = GradScaler()

    # Preprocess images to model input
    test_loader, test_dataset = _load_data(ibs, aid_list, config, multithread)

    # Compute embeddings
    embeddings = []
    model.eval()
    with torch.no_grad():
        for images, names, image_paths, image_bboxes, image_thetas in test_loader:
            if config.use_gpu:
                images = images.cuda(non_blocking=True)

            with autocast():
                output = model(images.float())

            embeddings.append(output.detach().cpu().numpy())

    embeddings = np.concatenate(embeddings)
    return embeddings


class MiewIdConfig(dt.Config):  # NOQA
    def get_param_info_list(self):
        return [
            ut.ParamInfo('config_path', None),
            ut.ParamInfo('use_knn', True, hideif=True),
        ]


def get_match_results(depc, qaid_list, daid_list, score_list, config):
    """ converts table results into format for ipython notebook """
    # qaid_list, daid_list = request.get_parent_rowids()
    # score_list = request.score_list
    # config = request.config

    unique_qaids, groupxs = ut.group_indices(qaid_list)
    # grouped_qaids_list = ut.apply_grouping(qaid_list, groupxs)
    grouped_daids = ut.apply_grouping(daid_list, groupxs)
    grouped_scores = ut.apply_grouping(score_list, groupxs)

    ibs = depc.controller
    unique_qnids = ibs.get_annot_nids(unique_qaids)

    # scores
    _iter = zip(unique_qaids, unique_qnids, grouped_daids, grouped_scores)
    for qaid, qnid, daids, scores in _iter:
        dnids = ibs.get_annot_nids(daids)

        # Remove distance to self
        annot_scores = np.array(scores)
        daid_list_ = np.array(daids)
        dnid_list_ = np.array(dnids)

        is_valid = daid_list_ != qaid
        daid_list_ = daid_list_.compress(is_valid)
        dnid_list_ = dnid_list_.compress(is_valid)
        annot_scores = annot_scores.compress(is_valid)

        # Hacked in version of creating an annot match object
        match_result = wbia.AnnotMatch()
        match_result.qaid = qaid
        match_result.qnid = qnid
        match_result.daid_list = daid_list_
        match_result.dnid_list = dnid_list_
        match_result._update_daid_index()
        match_result._update_unique_nid_index()

        grouped_annot_scores = vt.apply_grouping(annot_scores, match_result.name_groupxs)
        name_scores = np.array([np.max(dists) for dists in grouped_annot_scores])
        match_result.set_cannonical_name_score(annot_scores, name_scores)
        yield match_result


class MiewIdRequest(dt.base.VsOneSimilarityRequest):
    _symmetric = False
    _tablename = 'MiewId'

    @ut.accepts_scalar_input
    def get_fmatch_overlayed_chip(request, aid_list, overlay=True, config=None):
        depc = request.depc
        ibs = depc.controller
        chips = ibs.get_annot_chips(aid_list)
        return chips

    def render_single_result(request, cm, aid, **kwargs):
        # Returns match images side-by-side without activation overlay
        overlay = kwargs.get('draw_fmatches')
        chips = request.get_fmatch_overlayed_chip(
            [cm.qaid, aid], overlay=overlay, config=request.config
        )
        out_image = vt.stack_image_list(chips)

        return out_image

    # def render_single_result(request, cm, aid, **kwargs):

    #     depc = request.depc
    #     ibs = depc.controller

    #     # Load config
    #     species = ibs.get_annot_species_texts(aid)

    #     config = None
    #     if config is None:
    #         config = CONFIGS[species]
    #     config = _load_config(config)

    #     # Load model
    #     model = _load_model(config, MODELS[species], use_dataparallel=False)

    #     # This list has to be in the format of [query_aid, db_aid]
    #     aid_list = [cm.qaid, aid]
    #     test_loader, test_dataset = _load_data(ibs, aid_list, config)

    #     out_image = draw_one(config, test_loader,  model, images_dir = '', method='gradcam_plus_plus', eigen_smooth=False, show=False)

    #     return out_image

    def render_batch_result(request, cm, aids):

        depc = request.depc
        ibs = depc.controller

        # Load config
        species = ibs.get_annot_species_texts(aids)[0]

        config = None
        if config is None:
            config = CONFIGS[species]
        config = _load_config(config)

        # Load model
        model = _load_model(config, MODELS[species], use_dataparallel=False)

        # This list has to be in the format of [query_aid, db_aid]
        aid_list = np.concatenate(([cm.qaid],  aids))
        test_loader, test_dataset = _load_data(ibs, aid_list, config)

        batch_images = draw_batch(config, test_loader,  model, images_dir = '', method='gradcam_plus_plus', eigen_smooth=False, show=False)

        return batch_images
    
    def postprocess_execute(request, table, parent_rowids, rowids, result_list):
        qaid_list, daid_list = list(zip(*parent_rowids))
        score_list = ut.take_column(result_list, 0)
        depc = request.depc
        config = request.config
        cm_list = list(get_match_results(depc, qaid_list, daid_list, score_list, config))
        table.delete_rows(rowids)
        return cm_list

    def execute(request, *args, **kwargs):
        # kwargs['use_cache'] = False
        result_list = super(MiewIdRequest, request).execute(*args, **kwargs)
        qaids = kwargs.pop('qaids', None)
        if qaids is not None:
            result_list = [result for result in result_list if result.qaid in qaids]
        return result_list


@register_preproc_annot(
    tablename='MiewId',
    parents=[ANNOTATION_TABLE, ANNOTATION_TABLE],
    colnames=['score'],
    coltypes=[float],
    configclass=MiewIdConfig,
    requestclass=MiewIdRequest,
    fname='miew_id',
    rm_extern_on_delete=True,
    chunksize=None,
)
def wbia_plugin_miew_id(depc, qaid_list, daid_list, config):
    ibs = depc.controller

    qaids = list(set(qaid_list))
    daids = list(set(daid_list))

    use_knn = config.get('use_knn', True)

    qaid_score_dict = {}
    for qaid in tqdm.tqdm(qaids):
        if use_knn:
                miew_id_dists = ibs.miew_id_predict_light(
                    qaid,
                    daids,
                    config['config_path'],
                )
                miew_id_scores = distance_dicts_to_score_dicts(miew_id_dists)

                # aid_score_list = aid_scores_from_name_scores(ibs, miew_id_name_scores, daids)
                aid_score_list = aid_scores_from_score_dict(miew_id_scores, daids)
                aid_score_dict = dict(zip(daids, aid_score_list))

                qaid_score_dict[qaid] = aid_score_dict
        else:
            miew_id_annot_distances = ibs.miew_id_predict_light_distance(
                qaid,
                daids,
                config['config_path'],
            )
            qaid_score_dict[qaid] = {}
            for daid, miew_id_annot_distance in zip(daids, miew_id_annot_distances):
                qaid_score_dict[qaid][daid] = distance_to_score(miew_id_annot_distance)

    for qaid, daid in zip(qaid_list, daid_list):
        if qaid == daid:
            daid_score = 0.0
        else:
            aid_score_dict = qaid_score_dict.get(qaid, {})
            daid_score = aid_score_dict.get(daid)
        yield (daid_score,)


@register_ibs_method
def evaluate_distmat(ibs, aid_list, config, use_depc, ranks=[1, 5, 10, 20]):
    """Evaluate 1vsall accuracy of matching on annotations by
    computing distance matrix.
    """
    embs = np.array(miew_id_embedding(ibs, aid_list, config, use_depc))
    print('Computing distance matrix ...')
    distmat = compute_distance_matrix(embs, embs, metric='cosine')

    print('Computing ranks ...')
    db_labels = np.array(ibs.get_annot_name_rowids(aid_list))
    cranks, mAP = eval_onevsall(distmat, db_labels)

    print('** Results **')
    print('mAP: {:.1%}'.format(mAP))
    for r in ranks:
        print('Rank-{:<3}: {:.1%}'.format(r, cranks[r - 1]))
    return cranks[0]


def _load_config(config_url):
    r"""
    Load a configuration file
    """
    config_fname = config_url.split('/')[-1]
    config_file = ut.grab_file_url(
        config_url, appname='wbia_miew_id', check_hash=False, fname=config_fname
    )

    config = get_config(config_file)
    config.use_gpu = torch.cuda.is_available()
    config.engine.device = 'cuda' if config.use_gpu else 'cpu'
    # config.merge_from_file(config_file)
    return config


def _load_model(config, model_url, use_dataparallel=True):
    r"""
    Load a model based on config file
    """
    # print('Building model: {}'.format(config.model.name))
    # model = build_model(
    #     name=config.model.name,
    #     num_classes=config.model.num_train_classes,
    #     loss=config.loss.name,
    #     pretrained=config.model.pretrained,
    #     use_gpu=config.use_gpu,
    # )

    # Download the model weights
    model_fname = model_url.split('/')[-1]
    model_path = ut.grab_file_url(
        model_url, appname='wbia_miew_id', check_hash=False, fname=model_fname
    )

    # load_pretrained_weights(model, model_path)

    model = get_model(config, model_path)

    # if config.use_gpu:
    #    model.load_state_dict(torch.load(model_path))
    # else:
    #    model.load_state_dict(torch.load(model_path, map_location=torch.device('cpu')))
    # print('Loaded model from {}'.format(model_path))
    if config.use_gpu and use_dataparallel:
        model = torch.nn.DataParallel(model).cuda()
    return model


def _load_data(ibs, aid_list, config, multithread=False):
    r"""
    Load data, preprocess and create data loaders
    """

    test_transform = get_test_transforms(config)
    image_paths = ibs.get_annot_image_paths(aid_list)
    bboxes = ibs.get_annot_bboxes(aid_list)
    names = ibs.get_annot_name_rowids(aid_list)
    viewpoints = ibs.get_annot_viewpoints(aid_list)
    thetas = ibs.get_annot_thetas(aid_list)
    chips = ibs.get_annot_chips(aid_list)

    dataset = PluginDataset(
        chips,
        image_paths,
        names,
        bboxes,
        viewpoints,
        thetas,
        test_transform,
        fliplr=config.test.fliplr,
        fliplr_view=config.test.fliplr_view,
        use_chips=True
    )

    if multithread:
        num_workers = config.data.workers
    else:
        num_workers = 0

    dataloader = torch.utils.data.DataLoader(
        dataset,
        batch_size=config.test.batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True,
        drop_last=False,
    )
    print('Loaded {} images for model evaluation'.format(len(dataset)))

    return dataloader, dataset


def wbia_miew_id_test_ibs(demo_db_url, species, subset):
    r"""
    Create a database to test orientation detection from a coco annotation file
    """
    testdb_name = 'testdb_{}_{}'.format(species, subset)

    test_ibs = wbia.opendb(testdb_name, allow_newdir=True)
    if len(test_ibs.get_valid_aids()) > 0:
        return test_ibs
    else:
        # Download demo data archive
        db_dir = ut.grab_zipped_url(demo_db_url, appname='wbia_miew_id')

        # Load coco annotations
        json_file = os.path.join(
            db_dir, 'annotations', 'instances_{}.json'.format(subset)
        )
        coco = read_json(json_file)
        coco_annots = coco['annotations']
        coco_images = coco['images']
        print('Found {} records in demo db'.format(len(coco_annots)))

        # Parse COCO annotations
        id2file = {a['id']: a['file_name'] for a in coco_images}
        files = [id2file[a['image_id']] for a in coco_annots]
        # Get image paths and add them to the database
        gpaths = [os.path.join(db_dir, 'images', subset, f) for f in files]
        names = [a['name'] for a in coco_annots]
        if 'viewpoint' in coco_annots[0]:
            viewpoint_list = [a['viewpoint'] for a in coco_annots]
        else:
            viewpoint_list = None

        # Add files and names to db
        gid_list = test_ibs.add_images(gpaths)
        nid_list = test_ibs.add_names(names)
        species = [species] * len(gid_list)

        # these images are pre-cropped aka trivial annotations
        bbox_list = [a['bbox'] for a in coco_annots]
        test_ibs.add_annots(
            gid_list,
            bbox_list=bbox_list,
            species_list=species,
            nid_list=nid_list,
            viewpoint_list=viewpoint_list,
        )

        return test_ibs


@register_ibs_method
def miew_id_predict_light(ibs, qaid, daid_list, config=None):
    db_embs = np.array(ibs.miew_id_embedding(daid_list, config))
    query_emb = np.array(ibs.miew_id_embedding([qaid], config))

    # db_labels = np.array(ibs.get_annot_name_texts(daid_list, distinguish_unknowns=True))
    db_labels = np.array(daid_list)

    ans = pred_light(query_emb, db_embs, db_labels)
    return ans


@register_ibs_method
def miew_id_predict_light_distance(ibs, qaid, daid_list, config=None):
    assert len(daid_list) == len(set(daid_list))
    db_embs = np.array(ibs.miew_id_embedding(daid_list, config))
    query_emb = np.array(ibs.miew_id_embedding([qaid], config))

    input1 = torch.Tensor(query_emb)
    input2 = torch.Tensor(db_embs)
    distmat = compute_distance_matrix(input1, input2, metric='cosine')
    distances = np.array(distmat[0])
    return distances


def _miew_id_accuracy(ibs, qaid, daid_list):
    daids = daid_list.copy()
    daids.remove(qaid)
    ans = ibs.miew_id_predict_light(qaid, daids)
    ans_names = [row['label'] for row in ans]
    ground_truth = ibs.get_annot_name_texts(qaid)
    try:
        rank = ans_names.index(ground_truth) + 1
    except ValueError:
        rank = -1
    print('rank %s' % rank)
    return rank


def miew_id_mass_accuracy(ibs, aid_list, daid_list=None):
    if daid_list is None:
        daid_list = aid_list
    ranks = [_miew_id_accuracy(ibs, aid, daid_list) for aid in aid_list]
    return ranks


def accuracy_at_k(ibs, ranks, max_rank=10):
    counts = [ranks.count(i) for i in range(1, max_rank + 1)]
    percent_counts = [count / len(ranks) for count in counts]
    cumulative_percent = [
        sum(percent_counts[:i]) for i in range(1, len(percent_counts) + 1)
    ]
    return cumulative_percent


def subset_with_resights(ibs, aid_list, n=3):
    names = ibs.get_annot_name_rowids(aid_list)
    name_counts = _count_dict(names)
    good_annots = [aid for aid, name in zip(aid_list, names) if name_counts[name] >= n]
    return good_annots


def _count_dict(item_list):
    from collections import defaultdict

    count_dict = defaultdict(int)
    for item in item_list:
        count_dict[item] += 1
    return dict(count_dict)


def subset_with_resights_range(ibs, aid_list, min_sights=3, max_sights=10):
    name_to_aids = _name_dict(ibs, aid_list)
    final_aids = []
    import random

    for name, aids in name_to_aids.items():
        if len(aids) < min_sights:
            continue
        elif len(aids) <= max_sights:
            final_aids += aids
        else:
            final_aids += sorted(random.sample(aids, max_sights))
    return final_aids


@register_ibs_method
def miew_id_new_accuracy(ibs, aid_list, min_sights=3, max_sights=10):
    aids = subset_with_resights_range(ibs, aid_list, min_sights, max_sights)
    ranks = miew_id_mass_accuracy(ibs, aids)
    accuracy = accuracy_at_k(ibs, ranks)
    print(
        'Accuracy at k for annotations with %s-%s sightings:' % (min_sights, max_sights)
    )
    print(accuracy)
    return accuracy


# The following functions are comiew_idd from TBD v1 because these functions
# are agnostic tot eh method of computing embeddings:
# https://github.com/WildMeOrg/wbia-plugin-miew_id/wbia_miew_id/_plugin.py
def _db_labels_for_miew_id(ibs, daid_list):
    db_labels = ibs.get_annot_name_texts(daid_list, distinguish_unknowns=True)
    # db_auuids = ibs.get_annot_name_rowids(daid_list)
    # # later we must know which db_labels are for single auuids, hence prefix
    # db_auuids = [UNKNOWN + '-' + str(auuid) for auuid in db_auuids]
    # db_labels = [
    #     lab if lab is not UNKNOWN else auuid for lab, auuid in zip(db_labels, db_auuids)
    # ]
    db_labels = np.array(db_labels)
    return db_labels



# def distance_to_score(distance, norm=2.0):
#     # score = 1 / (1 + distance)
#     score = np.exp(-distance / norm)
#     return score

# for cosine distance
def distance_to_score(distance):
    score = (2 - distance) / 2
    score = np.float64(score)
    return score

def distance_dicts_to_score_dicts(distance_dicts, conversion_func=distance_to_score):
    score_dicts = distance_dicts.copy()
    name_score_dicts = {}
    for entry in score_dicts:
        name_score_dicts[entry['label']] = conversion_func(entry['distance'])
    return name_score_dicts

def aid_scores_from_score_dict(name_score_dict, daid_list):
    daid_scores = [name_score_dict.get(daid, 0) for daid in daid_list]
    return daid_scores

def aid_scores_from_name_scores(ibs, name_score_dict, daid_list):
    daid_name_list = list(_db_labels_for_miew_id(ibs, daid_list))

    name_count_dict = {
        name: daid_name_list.count(name) for name in name_score_dict.keys()
    }

    name_annotwise_score_dict = {
        name: name_score_dict[name] / name_count_dict[name]
        for name in name_score_dict.keys()
    }

    from collections import defaultdict

    name_annotwise_score_dict = defaultdict(float, name_annotwise_score_dict)

    # bc daid_name_list is in the same order as daid_list
    daid_scores = [name_annotwise_score_dict[name] for name in daid_name_list]
    return daid_scores


if __name__ == '__main__':
    r"""
    CommandLine:
        python -m wbia_miew_id._plugin --allexamples
    """
    import multiprocessing

    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA

    ut.doctest_funcs()
