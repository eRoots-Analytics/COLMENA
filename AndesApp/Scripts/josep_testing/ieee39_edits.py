import andes
import matplotlib

from andes.utils.paths import get_case

andes.config_logger(stream_level=20)

ss = andes.run(get_case('kundur/kundur_full.xlsx'), default_config=True)

ss.TDS.config.tf = 10  # simulate for 10 seconds


matplotlib.use('TkAgg')
ss.TDS.run()
ss.exit_code
ss.TDS.load_plotter()
fig, ax = ss.TDS.plt.plot((5, 6, 7, 8))