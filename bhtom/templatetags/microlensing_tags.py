# importing the required module
import logging
from os import path

from django import template
import csv
import math
import numpy as np
from guardian.shortcuts import get_objects_for_user
from scipy import optimize
from datetime import date
import time
import pandas as pd
import warnings
import plotly.graph_objs as go
from plotly import offline
import json
from bhtom.models import ViewReducedDatum

from django.conf import settings

logger = logging.getLogger(__name__)
register = template.Library()


@register.inclusion_tag('tom_dataproducts/partials/microlensing_for_target.html', takes_context=True)
def microlensing_for_target(context, target, slevel, clevel):
    if settings.TARGET_PERMISSIONS_ONLY:
        datums = ViewReducedDatum.objects.filter(target=target,
                                                 data_type__in=[
                                                     settings.DATA_PRODUCT_TYPES['photometry'][0]])

    else:
        datums = get_objects_for_user(context['request'].user,
                                      'bhtom_viewreduceddatum',
                                      klass=ViewReducedDatum.objects.filter(
                                          target=target,
                                          data_type__in=[settings.DATA_PRODUCT_TYPES['photometry'][0]]))
    X = []
    Y = []
    err = []
    X_timestamp = []
    X_fit_timestamp = []

    for datum in datums:
        if type(datum.value) is dict:
            values = datum.value
        else:
            values = json.loads(datum.value)

        extra_data = json.loads(datum.rd_extra_data) if datum.rd_extra_data is not None else {}
        if str(extra_data.get('facility')) == "Gaia":
            try:
                X.append(float(values.get('jd')))
                X_timestamp.append(datum.timestamp)
                Y.append(float(values.get('magnitude')))
                err.append(calculate_error(float(values.get('magnitude'))))
            except Exception:
                continue
    if slevel == '':
        slevel = '0.05'
    if clevel == '':
        clevel = '0.05'
    alfa = float(slevel)
    errorSignificance = float(clevel)
    # reading file and data to plot

    try:
        chi2_file_path = path.join(settings.BASE_DIR, 'bhtom/chi2.csv')
    except Exception as e:
        return {
            'errors': "ERROR: No chi2 file found",
        }

    y = np.asarray(Y)
    x = np.asarray(X)
    x_timestamp = np.asarray(X_timestamp)
    if len(x) == 0:  # checking if there is Gaia data
        return {
            'errors': "ERROR: No Gaia data",
        }
    else:
        # title
        # get time of modeling
        start_time = time.time()
        # ulensing modelling
        t0 = x[-1]
        chi2_best = 100000
        mchi2_best = 100000
        NDF = 0
        errors = ''
        for i in range(10, 600, 25):
            for j in [0.1, 0.01]:
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")  # supressing covariance warning
                        popt, pcov = optimize.curve_fit(ulens, xdata=x, ydata=y, p0=np.asarray([t0, i, j, y.max()]))
                except RuntimeError as error:
                    pass
                # chi^2 test
                try:
                    chi2 = lambda popt, x, y, err: sum(((ulens(x, *popt) - y) / err) ** 2)
                    tmp1 = chi2(popt, x, y, err)
                    tmp2 = chi2(popt, x, y, err) / (len(x) - 4)
                    tmp = np.asarray(pcov)
                    if mchi2_best > tmp2 and not np.isinf(tmp).any():
                        chi2_best = tmp1
                        mchi2_best = tmp2
                        popt_best = popt
                        pcov_best = pcov
                        NDF = len(x) - 4
                except ZeroDivisionError as error:
                    return {
                        'errors': "ERROR: Divide by 0! The error of y is 0!",
                    }
                except UnboundLocalError as error:
                    pass
        if NDF <= 250:
            round_NDF = NDF
        elif 250 < NDF <= 1000:
            round_NDF = myround(NDF)
        else:
            round_NDF = 1000
            errors = "ERROR: NDF out of range"
        chi2_table = 0
        with open(chi2_file_path, 'r') as csvfile:
            plots2 = csv.reader(csvfile, delimiter=',')
            for row in plots2:
                if row[0] == str(round_NDF):
                    dict_chi = {
                        0.995: float(row[1]),
                        0.975: float(row[2]),
                        0.2: float(row[3]),
                        0.1: float(row[4]),
                        0.05: float(row[5]),
                        0.025: float(row[6]),
                        0.02: float(row[7]),
                        0.01: float(row[8]),
                        0.005: float(row[9]),
                        0.002: float(row[10]),
                        0.001: float(row[11]),
                    }
                    chi2_table = dict_chi[alfa]
            csvfile.close()
        info_conclusion = ''
        if chi2_best <= chi2_table:
            info_conclusion = "There is NO reason to reject the hypothesis - this phenomenon may be microlensing at the expected confidence level: " + str(
                100 - alfa * 100) + "%"
        else:
            info_conclusion = "There is a reason for rejecting the hypothesis - This phenomenon CANNOT be microlensing at the expected confidence level: " + str(
                100 - alfa * 100) + "%"

            # time of miscrolensing and max magnitude
        microlensing_start_time = 0
        microlensing_end_time = 0
        max_mag = 1000  # big number because of inversion

        max_mag_time = 0
        beg = False
        fin = False
        deviation = 0.999  # when mag decrease 0.1%
        t = x[0]
        info_start_time = ''
        info_start_time_value = ''
        info_end_time = ''
        info_end_time_value = ''
        while (beg == False or fin == False) and t < x[0] + 10000:
            if ulens(t, *popt_best) <= ulens(x[0], *popt_best) * deviation and beg == False:
                microlensing_start_time = t
                info_start_time = "Microlensing start time: "
                info_start_time_value = str(jd_to_date(microlensing_start_time)) + " |" + str(
                    microlensing_start_time)
                beg = True
            elif ulens(t, *popt_best) > ulens(microlensing_start_time, *popt_best) and beg == True and fin == False:
                microlensing_end_time = t
                info_end_time = "Microlensing end time: "
                info_end_time_value = str(jd_to_date(microlensing_end_time)) + " |" + str(microlensing_end_time)
                fin = True
            t += 0.5

        # fit with prediction
        time_plot = np.linspace(x[0], microlensing_end_time + 366, 1000)
        # showing date on x axis
        for i in range(len(time_plot) - 1):
            tmp_2 = jd_to_date(time_plot[i])
            dt = str(tmp_2[0]) + "-" + str(tmp_2[1]) + "-" + str(tmp_2[2])
            X_timestamp.append(pd.to_datetime(dt))
            X_fit_timestamp.append(pd.to_datetime(dt))
            if ulens(time_plot[i], *popt_best) <= max_mag and beg == True and fin == True:
                    max_mag = ulens(time_plot[i], *popt_best)
                    max_mag_time = time_plot[i]
        time_plot_timestamp = np.asarray(X_fit_timestamp)

        if fin == True and beg == True:
            a = date(*jd_to_date(microlensing_start_time))
            b = date(*jd_to_date(microlensing_end_time))
            c = date.today()
            max_mag = '{0:.3f}'.format(max_mag)
            info_duration = "Duration of microlensing: "
            info_duration_value = str(days_to_ymd((b - a).days))
            info_remainingTime = "Remaining time of microlensing: "
            if (b - c).days > 0:
                info_remainingTime_value = str(days_to_ymd((b - c).days))
            else:
                info_remainingTime_value = "-"
            info_maximumMagnitude = "Maximum magnitude: "
            info_maximumMagnitude_value = "%s mag" % max_mag
            info_maximumMagnitudeTime = "Expected time of maximum: "
            info_maximumMagnitudeTime_value = str(jd_to_date(max_mag_time)) + " |" + str(max_mag_time)
            # print fitted parameters
            if abs(np.sqrt(pcov_best[0][0]) / popt_best[0]) <= errorSignificance:
                info_t0 = "t0: " + str('{0:.3f}'.format(popt_best[0])) + " (" + str(
                    '{0:.3f}'.format(np.sqrt(pcov_best[0][0]))) + ")"
                info_t0_check = "OK"
            else:
                info_t0 = "t0: " + str('{0:.3f}'.format(popt_best[0])) + " (" + str(
                    '{0:.3f}'.format(np.sqrt(pcov_best[0][0]))) + ")"
                info_t0_check = "BIGGER THAN " + str(errorSignificance * 100) + "%"

            if abs(np.sqrt(pcov_best[1][1]) / popt_best[1]) <= errorSignificance:
                info_te = "te: " + str('{0:.3f}'.format(popt_best[1])) + " (" + str(
                    '{0:.3f}'.format(np.sqrt(pcov_best[1][1]))) + ")"
                info_te_check = "OK"
            else:
                info_te = "te: " + str('{0:.3f}'.format(popt_best[1])) + " (" + str(
                    '{0:.3f}'.format(np.sqrt(pcov_best[1][1]))) + ")"
                info_te_check = "BIGGER THAN " + str(errorSignificance * 100) + "%"

            if abs(np.sqrt(pcov_best[2][2]) / popt_best[2]) <= errorSignificance:
                info_u0 = "u0: " + str('{0:.5f}'.format(abs(popt_best[2]))) + " (" + str(
                    '{0:.3f}'.format(np.sqrt(pcov_best[2][2]))) + ")"
                info_u0_check = "OK"
            else:
                info_u0 = "u0: " + str('{0:.5f}'.format(abs(popt_best[2]))) + " (" + str(
                    '{0:.3f}'.format(np.sqrt(pcov_best[2][2]))) + ")"
                info_u0_check = "BIGGER THAN " + str(errorSignificance * 100) + "%"

            if abs(np.sqrt(pcov_best[3][3]) / popt_best[3]) <= errorSignificance:
                info_I0 = "I0: " + str('{0:.3f}'.format(popt_best[3])) + " (" + str(
                    '{0:.3f}'.format(np.sqrt(pcov_best[3][3]))) + ")"
                info_I0_check = "OK"
            else:
                info_I0 = "I0: " + str('{0:.3f}'.format(popt_best[3])) + " (" + str(
                    '{0:.3f}'.format(np.sqrt(pcov_best[3][3]))) + ")"
                info_I0_check = "BIGGER THAN " + str(errorSignificance * 100) + "%"
            info_fs = "fs: 1.0 (fixed)"

            # execution time
            info_executionTime = "Time of fitting execution: %s seconds" % '{0:.3f}'.format(
                (time.time() - start_time))
        else:
            return {
                'errors': "ERROR: Cannot find fitted parameters",
            }
        # plotting fig
        plot_data = [go.Scatter(
            x=x_timestamp,
            y=y,
            mode='markers',
            name="Experimental data with error bar",
            error_y=dict(type='data',
                         array=err,
                         visible=True),
        ), go.Scatter(
            x=time_plot_timestamp,
            y=ulens(time_plot, *popt_best),
            mode='lines',
            line=dict(shape='spline', smoothing=1.3),
            name="Fit with prediction",
        )
        ]
        layout = go.Layout(
            title=dict(text=str(target)),
            yaxis=dict(autorange='reversed', title='Magnitude [mag]'),
            xaxis=dict(title='UTC time'),
            height=600,
            width=700,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

    return {
        'errors': errors,
        'target': target,
        'confidenceLevel_value': str('{0:.3f}'.format(1 - alfa)),
        'significanceLevel_value': str('{0:.3f}'.format(alfa)),
        'maximumError_value': str('{0:.2f}'.format(errorSignificance)),
        'criticalLevel': "Critical level: ",
        'criticalLevel_value': str('{0:.3f}'.format(chi2_table)),
        'Chi2Test': "Chi2 test: ",
        'Chi2Test_value': str('{0:.3f}'.format(chi2_best)),
        'NDF': 'NDF: ',
        'NDF_value': str(NDF),
        'Chi2NDF': "Chi2/NDF: ",
        'Chi2NDF_value': str('{0:.3f}'.format(mchi2_best)),
        'conclusion': info_conclusion,
        'plot': offline.plot(go.Figure(data=plot_data, layout=layout), output_type='div', show_link=False),
        'microStartTime': info_start_time,
        'microStartTime_value': info_start_time_value,
        'microEndTime': info_end_time,
        'microEndTime_value': info_end_time_value,
        'duration': info_duration,
        'duration_value': info_duration_value,
        'remainingTime': info_remainingTime,
        'remainingTime_value': info_remainingTime_value,
        'maximumMagnitude': info_maximumMagnitude,
        'maximumMagnitude_value': info_maximumMagnitude_value,
        'maximumMagnitudeTime': info_maximumMagnitudeTime,
        'maximumMagnitudeTime_value': info_maximumMagnitudeTime_value,
        't0': info_t0,
        't0_check': info_t0_check,
        'te': info_te,
        'te_check': info_te_check,
        'u0': info_u0,
        'u0_check': info_u0_check,
        'I0': info_I0,
        'I0_check': info_I0_check,
        'fs': info_fs,
        'executionTime': info_executionTime,
    }


# classical lens, no effects
def ulens(t, t0, te, u0, I0, fs=1):
    tau = (t - t0) / te
    x = tau
    y = u0
    u = np.sqrt(x * x + y * y)
    ampl = (u * u + 2) / (u * np.sqrt(u * u + 4))
    F = ampl * fs + (1 - fs)
    I = I0 - 2.5 * np.log10(F)
    return I


# convert Julian Day to date
def jd_to_date(jd):
    jd = jd + 0.5
    F, I = math.modf(jd)
    I = int(I)
    A = math.trunc((I - 1867216.25) / 36524.25)
    if I > 2299160:
        B = I + 1 + A - math.trunc(A / 4.)
    else:
        B = I
    C = B + 1524
    D = math.trunc((C - 122.1) / 365.25)
    E = math.trunc(365.25 * D)
    G = math.trunc((C - E) / 30.6001)
    day = C - E + F - math.trunc(30.6001 * G)
    if G < 13.5:
        month = G - 1
    else:
        month = G - 13
    if month > 2.5:
        year = D - 4716
    else:
        year = D - 4715
    d = date(int(year), int(month), int(np.floor(day)))
    return (d.year, d.month, d.day)


def date_to_jd(year, month, day):
    if month == 1 or month == 2:
        yearp = year - 1
        monthp = month + 12
    else:
        yearp = year
        monthp = month

    # this checks where we are in relation to October 15, 1582, the beginning
    # of the Gregorian calendar.
    if ((year < 1582) or
            (year == 1582 and month < 10) or
            (year == 1582 and month == 10 and day < 15)):
        # before start of Gregorian calendar
        B = 0
    else:
        # after start of Gregorian calendar
        A = math.trunc(yearp / 100.)
        B = 2 - A + math.trunc(A / 4.)

    if yearp < 0:
        C = math.trunc((365.25 * yearp) - 0.75)
    else:
        C = math.trunc(365.25 * yearp)

    D = math.trunc(30.6001 * (monthp + 1))

    jd = B + C + D + day + 1720994.5
    return jd


# days to years, months and days
def days_to_ymd(number_of_days):
    years = number_of_days // 365
    months = (number_of_days - years * 365) // 30
    days = (number_of_days - years * 365 - months * 30)
    return years, months, days


# wartość błędu znaleziona empirycznie
def calculate_error(G):
    if G <= 13.5:
        return 10 ** (0.2 * 13.5 - 5.2)
    elif G > 13.5 and G < 17.0:
        return 10 ** (0.2 * G - 5.2)
    elif G >= 17.0:
        return 10 ** (0.26 * G - 6.26)
    else:
        return 0


# rounded to 50 up
def myround(x, base=50):
    return int(base * np.ceil(x / base))
