from pcmdi_metrics.PMP.PMPIO import *



class OBS(PMPIO):
    def __init__(self, root, var, obs_dict, obs='default',
                 file_mask_template=None):
        template = "%(realm)/%(frequency)/%(variable)/" +\
                   "%(reference)/%(ac)/%(filename)"
        super(OBS, self).__init__(root, template, file_mask_template)

        if obs not in obs_dict[var]:
            msg = '%s is not a valid obs according to the obs_dict.' % obs
            raise RuntimeError(msg)
        obs_name = obs_dict[var][obs]
        # Sometimes (when sftlf), we send the actually name of the obs
        if isinstance(obs_name, dict):
            obs_name = obs

        obs_table = obs_dict[var][obs_name]['CMIP_CMOR_TABLE']
        self.setup_based_on_obs_table(obs_table)

        self.filename = obs_dict[var][obs_name]['filename']
        self.reference = obs_name
        self.variable = var

    def setup_based_on_obs_table(self, obs_table):
        if obs_table == u'Omon':
            self.realm = 'ocn'
            self.frequency = 'mo'
            self.ac = 'ac'
        elif obs_table == u'fx':
            self.realm = ''
            self.frequency = 'fx'
            self.ac = ''
        else:
            self.realm = 'atm'
            self.frequency = 'mo'
            self.ac = 'ac'


class Observation(object):
    def __init__(self, parameter, var_name_long, region, obs, obs_dict):
        self.parameter = parameter
        self.level = self.calculate_level_from_var(var_name_long)
        self.var = var_name_long.split('_')[0]
        self.region = region
        self.obs = obs
        self.obs_dict = obs_dict
        self.obs_file = None
        self.sftlf = None
        self.create_obs_file()

    def __call__(self, *args, **kwargs):
        self.get()

    @staticmethod
    def calculate_level_from_var(var):
        var_split_name = var.split('_')
        if len(var_split_name) > 1:
            level = float(var_split_name[-1]) * 100
        else:
            level = None
        return level

    def create_obs_file(self):
        obs_mask_name = self.create_obs_mask_name()
        self.obs_file = OBS(self.parameter.obs_data_path, self.var,
                            self.obs_dict, self.obs,
                            file_mask_template=obs_mask_name)

        self.setup_obs_file(self.obs_file)



    def create_obs_mask_name(self):
        try:
            obs_from_obs_dict = self.get_obs_from_obs_dict()
            obs_mask = OBS(self.parameter.obs_data_path, 'sftlf',
                           self.obs_dict, obs_from_obs_dict['RefName'])
            obs_mask_name = obs_mask()
        except:
            msg = 'Could not figure out obs mask name from obs json file'
            logging.error(msg)
            obs_mask_name = None
        return obs_mask_name

    def get_obs_from_obs_dict(self):
        if self.obs not in self.obs_dict[self.var]:
           raise KeyError('The selected obs is not in the obs_dict')

        if isinstance(self.obs_dict[self.var][self.obs], (str, unicode)):
            obs_from_obs_dict = \
                self.obs_dict[self.var][self.obs_dict[self.var][self.obs]]
        else:
            obs_from_obs_dict = self.obs_dict[self.var][self.obs]
        return obs_from_obs_dict


    def setup_obs_file(self):
        regrid_method = ''
        regrid_tool = ''

        if self.use_omon():
            regrid_method = self.parameter.regrid_method_ocn
            regrid_tool = self.regrid_tool_ocn.regrid_tool
            self.obs_file.table = 'Omon'
            self.obs_file.realm = 'ocn'
        else:
            regrid_method = self.parameter.regrid_method
            regrid_tool = self.parameter.regrid_tool
            self.obs_file.table = 'Amon'
            self.obs_file.realm = 'atm'

        self.obs_file.set_target_grid(self.parameter.target_grid,
                                 regrid_tool,
                                 regrid_method)
        if self.region is not None:
            region_value = self.region.get('value', None)
            if region_value is not None:
                if self.sftlf is None:
                    self.sftlf = self.create_sftlf(self.parameter)
                self.obs_file.targetMask = MV2.not_equal(
                    self.sftlf['targetGrid'],
                    region_value
                )

    def use_omon(self):
        return \
            self.obs_dict[self.var][self.obs_dict[self.var]["default"]]\
                ["CMIP_CMOR_TABLE"] == 'Omon'

    @staticmethod
    def create_sftlf(parameter):
        sftlf = {}
        # LOOP THROUGH DIFFERENT MODEL VERSIONS OBTAINED FROM input_model_data.py
        for model_version in parameter.model_versions:
            sft = PMPIO(
                parameter.mod_data_path,
                getattr(
                    parameter,
                    "sftlf_filename_template",
                    parameter.filename_template))
            sft.model_version = model_version
            sft.table = "fx"
            sft.realm = "atmos"
            sft.period = parameter.period
            sft.ext = "nc"
            sft.case_id = parameter.case_id
            sft.targetGrid = None
            sft.realization = "r0i0p0"
            #applyCustomKeys(sft, parameter.custom_keys, "sftlf")
            try:
                sftlf[model_version] = {"raw": sft.get("sftlf")}
                sftlf[model_version]["filename"] = os.path.basename(sft())
                sftlf[model_version]["md5"] = sft.hash()
            except:
                # Hum no sftlf...
                sftlf[model_version] = {"raw": None}
                sftlf[model_version]["filename"] = None
                sftlf[model_version]["md5"] = None
        if parameter.targetGrid == "2.5x2.5":
            tGrid = cdms2.createUniformGrid(-88.875, 72, 2.5, 0, 144, 2.5)
        else:
            tGrid = parameter.targetGrid

        sft = cdutil.generateLandSeaMask(tGrid)
        sft[:] = sft.filled(1.) * 100.0
        sftlf["targetGrid"] = sft

        return sftlf

    def get(self):
        if self.level is not None:
            return self.obs_file.get(self.var, level=self.level,
                                     region=self.region)
        else:
            return self.obs_file.get(self.var, region=self.region)

    @staticmethod
    # This must remain static b/c used before an Observation obj is created.
    def setup_obs_list_from_parameter(parameter_obs_list, obs_dict, var):
        obs_list = parameter_obs_list
        if 'all' in [x.lower() for x in obs_list]:
            obs_list = 'all'
        if isinstance(obs_list, (unicode, str)):
            if obs_list.lower() == 'all':
                obs_list = []
                for obs in obs_dict[var].keys():
                    if isinstance(obs_dict[var][obs], (unicode, str)):
                        obs_list.append(obs)
            else:
                obs_list = [obs_list]
        return obs_list
