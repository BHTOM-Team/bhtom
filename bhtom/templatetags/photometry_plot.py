import json
from collections import namedtuple
from typing import Optional, List, Any

import dash
import requests

from dash import dcc, html
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from dash.dependencies import State
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import Output, Input
from django_common.auth_backends import User
from django_plotly_dash import DjangoDash
from tom_dataproducts.models import ReducedDatum
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q

from bhtom.models import refresh_reduced_data_view, Instrument, BHTomData
from bhtom.templatetags.photometry_tags import photometry_plot_data

import logging
logger = logging.getLogger(__name__)

try:
    from settings import local_settings as secret
except ImportError:
    secret = None


def read_secret(secret_key: str, default_value: Any = '') -> str:
    try:
        return getattr(secret, secret_key, default_value) if secret else default_value
    except:
        return default_value


PlotPointData = namedtuple('PlotPointData', ['reduced_datum', 'trace_index', 'point_index'])

app = DjangoDash(name='PhotometryPlot', external_stylesheets=[dbc.themes.BOOTSTRAP])

selected_point: Optional[PlotPointData] = None

previous_yes_n_clicks = 0
previous_no_n_clicks = 0

fig = go.Figure(data=[], layout=go.Layout(
    yaxis=dict(autorange='reversed'),
    xaxis=dict(title='UTC time'),
    height=600,
    width=750
))

app.layout = dbc.Spinner(dbc.Card([
    html.P("Click on the point to try to delete it."),
    dbc.Modal(
        [
            dbc.ModalBody("Do you want to delete this point?"),
            dbc.ModalFooter(
                [dbc.Button(
                    "Yes",
                    id='yes-delete-point',
                    className='ms-auto',
                    n_clicks=0
                ),
                    dbc.Button(
                        "No",
                        id='no-delete-point',
                        className='ms-auto',
                        n_clicks=0
                    ), ],
            )
        ],
        id='delete-point-modal',
        centered=True,
        is_open=False
    ),
    dcc.Input(id='target_id', persistence=False, value='', type='hidden'),
    dcc.Input(id='user_id', persistence=False, value='', type='hidden'),
    dcc.Graph(
        id='photometry-plot',
        figure=fig
    ),
    dbc.Alert("Point successfully deleted!", id='success_deleted', color="success", is_open=False),
    dbc.Alert("No permission to delete the point :(", id='no_permission', color="danger", is_open=False),
], body=True))


@app.callback(
    [Output("delete-point-modal", "is_open"),
     Output("success_deleted", "is_open"),
     Output("no_permission", "is_open"),
     Output("photometry-plot", "figure")],
    [Input("photometry-plot", "clickData"),
     Input("target_id", "value"),
     Input("user_id", "value"),
     Input("yes-delete-point", "n_clicks"),
     Input("no-delete-point", "n_clicks")],
    [State("delete-point-modal", "is_open"),
     State("success_deleted", "is_open"),
     State("no_permission", "is_open")],
)
def toggle_modal(clickData, target_id, user_id, yes_n_clicks, no_n_clicks,
                 delete_point_modal, success_deleted, no_permission):
    global selected_point, previous_target_name, previous_yes_n_clicks, previous_no_n_clicks

    ctx = dash.callback_context
    logger.info(f'[INTERACTIVE PLOT] Interactive plot triggered: {ctx.triggered}')

    # Update the data for new target
    if len(ctx.triggered) == 0:
        logger.info(f'[INTERACTIVE PLOT] Updating interactive plot for target_id: {target_id}')
        selected_point = None
        plot_data = photometry_plot_data(target_id=target_id, user_id=user_id)
        fig.data = []
        fig.add_traces(plot_data)
        fig.update_layout(transition_duration=500)

        return False, False, False, fig

    triggered = ctx.triggered[0]

    # A point has been clicked: check if the data is from either CPCS
    # or a file
    if triggered.get('prop_id') == 'photometry-plot.clickData':
        # Mark the clicked point as the selected one
        points_info_list = clickData.get('points', [])
        logger.info(f'[INTERACTIVE PLOT] A point has been clicked: {points_info_list}')
        if len(points_info_list) > 0:
            points_info = points_info_list[0]
            trace_index = points_info.get('curveNumber')
            point_index = points_info.get('pointIndex')
            timestamp = points_info.get('x')
            mag = points_info.get('y')
            filter = fig.data[trace_index].name

            logger.info(f'[INTERACTIVE PLOT] A point has been clicked: {points_info_list}')

            maybe_reduced_point: Optional[ReducedDatum] = try_to_fetch_point(target_id=target_id,
                                                                             point_timestamp=timestamp,
                                                                             point_mag=mag,
                                                                             point_band=filter)
            if maybe_reduced_point:

                logger.info(f'[INTERACTIVE PLOT] A reduced point has been fetched: {maybe_reduced_point}')

                selected_point = PlotPointData(reduced_datum=maybe_reduced_point,
                                               trace_index=trace_index,
                                               point_index=point_index)

                logger.info(f'[INTERACTIVE PLOT] A point on plot has been selected: {selected_point}')

                # Is the user superuser? Then she/he can delete everything
                if is_user_superuser(user_id):
                    logger.info(f'[INTERACTIVE PLOT] The user is a superuser.')

                    return True, False, False, fig

                # Is the selected point from CPCS? Then attempt deletion
                if is_point_from_cpcs(selected_point):
                    logger.info(f'[INTERACTIVE PLOT] The user is not a superuser, point is from CPCS.')

                    return True, False, False, fig

                # Is the selected point from file? Then check if the user is the owner
                if is_point_from_file(selected_point):
                    if check_if_file_owner_is_user(selected_point.reduced_datum, user_id):
                        logger.info(f'[INTERACTIVE PLOT] The user is not a superuser, point is from the user\'s file.')

                        return True, False, False, fig
                    else:
                        logger.info(f'[INTERACTIVE PLOT] The user is not a superuser, point is from someone else\'s file.')

                        selected_point = None
                        return False, False, True, fig

                # If none of these is true, then clear the selected point
                logger.info(f'[INTERACTIVE PLOT] Resetting the point.')
                selected_point = None
                raise PreventUpdate


    # Yes has been clicked on the delete point modal

    if triggered.get('prop_id') == 'yes-delete-point.n_clicks':
        logger.info(f'[INTERACTIVE PLOT] "Yes" has been clicked on the delete point modal for point {selected_point}.')

        # Check if there is a selected point
        if selected_point:
            logger.info(f'[INTERACTIVE PLOT] There is a selected point {selected_point}.')

            # If the selected point is from CPCS, then try to delete it
            if is_point_from_cpcs(selected_point):
                logger.info(f'[INTERACTIVE PLOT] Point to be deleted is from CPCS.')

                cpcs_id: int = int(selected_point.reduced_datum.source_location.split('&')[-1])
                logger.info(f'[INTERACTIVE PLOT] Point to be deleted has the CPCS id: {cpcs_id}.')

                hashtags: List[str] = fetch_hashtags_for_user(user_id)
                if try_to_delete_point_from_cpcs(hashtags, cpcs_id):
                    logger.info(f'[INTERACTIVE PLOT] The point with CPCS id {cpcs_id} has been deleted from CPCS.')

                    if try_to_delete_point_from_bhtom(selected_point):
                        logger.info(f'[INTERACTIVE PLOT] The point with CPCS id {cpcs_id} has been deleted from BHTOM.')

                        delete_from_plot(fig, selected_point)
                        logger.info(f'[INTERACTIVE PLOT] The point with CPCS id {cpcs_id} has been deleted from the plot.')

                        selected_point = None
                        return False, True, False, fig

                selected_point = None
                return False, False, True, fig

            elif is_point_from_file(selected_point):
                logger.info(f'[INTERACTIVE PLOT] The point to be deleted is from a file.')

                if is_user_superuser(user_id) or check_if_file_owner_is_user(selected_point.reduced_datum, user_id):
                    logger.info(f'[INTERACTIVE PLOT] The point to be deleted can be deleted by the user {user_id}.')

                    if try_to_delete_point_from_bhtom(selected_point):
                        logger.info(f'[INTERACTIVE PLOT] The point has been deleted from BHTOM.')

                        delete_from_plot(fig, selected_point)
                        logger.info(f'[INTERACTIVE PLOT] The point has been deleted from the plot.')

                        selected_point = None
                        return False, True, False, fig
                else:
                    selected_point = None
                    return False, False, True, fig

            selected_point = None
            return False, False, False, fig

    # No has been clicked on the delete point modal
    if triggered.get('prop_id') == 'no-delete-point.n_clicks':
        logger.info(f'[INTERACTIVE PLOT] "No" has been clicked on the delete point modal for point {selected_point}.')

        selected_point = None
        return False, False, False, fig

    raise PreventUpdate


def delete_from_plot(fig, selected_point: PlotPointData):
    new_x = list(fig.data[selected_point.trace_index]['x'])
    new_x.pop(selected_point.point_index)

    new_y = list(fig.data[selected_point.trace_index]['y'])
    new_y.pop(selected_point.point_index)

    fig.data[selected_point.trace_index]['x'] = tuple(new_x)
    fig.data[selected_point.trace_index]['y'] = tuple(new_y)
    fig.update_layout(transition_duration=500)


def is_user_superuser(user_id: int) -> bool:
    return User.objects.get(id=user_id).is_superuser


def is_point_from_cpcs(selected_point: PlotPointData) -> bool:
    return selected_point.reduced_datum.source_name == 'CPCS'


def is_point_from_file(selected_point: PlotPointData) -> bool:
    return selected_point.reduced_datum.source_name == '' and selected_point.reduced_datum.data_product_id is not None


def fetch_hashtags_for_user(user_id) -> List[str]:
    logger.info(f'[INTERACTIVE PLOT] Fetching hashtags for user {user_id}...')
    if is_user_superuser(user_id):
        hashtag = read_secret('CPCS_ADMIN_HASHTAG', '')
        return [hashtag]

    instruments = Instrument.objects.filter(user_id=user_id)
    logger.info(f'[INTERACTIVE PLOT] Found instruments for user {user_id}.')

    return [instrument.hashtag for instrument in instruments]


def try_to_delete_point_from_cpcs(hashtags, cpcs_id):
    for hashtag in hashtags:
        try:
            logger.info(f'[INTERACTIVE PLOT] Trying to delete point with CPCS id {cpcs_id} from CPCS.')
            response = requests.post(read_secret("CPCS_DELETE_POINT_URL"), {'hashtag': hashtag, 'followupid': cpcs_id})
            response.raise_for_status()
            return True
        except Exception as e:
            logger.info(f'[INTERACTIVE PLOT] Exception when deleteing point with CPCS id {cpcs_id} from CPCS: {e}')
            return False
    return False


def try_to_fetch_point(target_id, point_timestamp, point_mag, point_band) -> Optional[ReducedDatum]:
    from django.utils.timezone import make_aware

    logger.info(f'[INTERACTIVE PLOT] Fetching point with timestamp {point_timestamp} with band {point_band}')

    def load_datum_json(json_values):
        if json_values:
            if type(json_values) is dict:
                return json_values
            else:
                return json.loads(json_values.replace("\'", '"'))
        else:
            return {}

    timestamp = make_aware(datetime.strptime(point_timestamp, '%Y-%m-%d %H:%M:%S.%f'), timezone=timezone.utc)

    points_with_timestamp = ReducedDatum.objects.filter(Q(target_id=target_id,
                                                        timestamp__gte=timestamp - timedelta(milliseconds=10),
                                                        timestamp__lte=timestamp + timedelta(milliseconds=10)) &
                                                        (Q(source_name='CPCS') | Q(data_product__isnull=False)))

    for point in points_with_timestamp:
        try:
            value = load_datum_json(point.value)
            if value["magnitude"] == point_mag and value["filter"] == point_band:
                return point
        except Exception as e:
            logger.info(f'[INTERACTIVE PLOT] Exception when fetching point with timestamp {point_timestamp} '
                        f'with band {point_band}: {e}')
            return None


def check_if_file_owner_is_user(reduced_datum: ReducedDatum, user_id: int) -> bool:

    bhtom_data: BHTomData = BHTomData.objects.get(dataproduct_id_id=reduced_datum.data_product_id)

    if bhtom_data:
        return bhtom_data.user_id == user_id

    return False


def try_to_delete_point_from_bhtom(plot_point_data: PlotPointData) -> bool:
    try:
        plot_point_data.reduced_datum.delete()
        refresh_reduced_data_view()
        return True
    except Exception as e:
        return False
