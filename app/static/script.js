function authenticateRecharge(rechargeId) {
    $.ajax({
        url: `/update_recharge/${rechargeId}/`,
        type: 'POST',
        data: {
            csrfmiddlewaretoken: getCookie('csrftoken'),
        },
        success: function(response) {
            // Inject status and message into the HTML
            document.getElementById('status-span').innerText = response.status;
            document.getElementById('message-span').innerText = response.message;

            if(response.status === "success") {
                document.getElementById('btn-authenticate-' + rechargeId).style.display = 'none';
            }
        },
        error: function(error) {
            console.log(error);
            // You can also update the status and message for error cases
            document.getElementById('status-span').innerText = 'error';
            document.getElementById('message-span').innerText = 'An error occurred during the request.';
        }
    });
}


// Function to get CSRF token from cookies
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}


function passwordViewLogin() {
    var passwordInput = document.getElementById("exampleInputPassword1");
    var checkbox = document.getElementById("exampleCheck1");

    if (checkbox.checked){
        passwordInput.type = "text";
    } else {
        passwordInput.type = "password";
    }
}

function passwordViewRegister() {
    var password1 = document.getElementById("password1");
    var password2 = document.getElementById("password2");
    var checkbox = document.getElementById("exampleCheck1");

    if (checkbox.checked) {
        password1.type = "text";
        password2.type = "text";
    } else {
        password1.type = "password";
        password2.type = "password";
    }
}
