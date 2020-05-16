function dataProductSelect() {

    var data_type_0 = document.getElementById("id_data_product_type_0").checked;
    var data_type_1 = document.getElementById("id_data_product_type_1").checked;
    var mjd = document.getElementById("mjd");
    var ExpTime = document.getElementById("ExpTime");
    var instrument = document.getElementById("id_instrument");

    if (data_type_0 == true){
        mjd.setAttribute("required", true);
        ExpTime.setAttribute("required", true);
    }
    else{
        mjd.removeAttribute("required");
        ExpTime.removeAttribute("required");
    }

    if (data_type_1== true){
        instrument.setAttribute("required", true);
    }
    else{
        instrument.removeAttribute("required");
    }

}
