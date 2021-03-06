package com.google.appengine.api.users.dev;


import java.io.IOException;
import java.io.PrintWriter;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;


/*
 * AppScale replaced class
 */
public final class LocalLoginServlet extends HttpServlet
{
    private static final long   serialVersionUID    = 1L;
    private static final String LOGIN_SERVER        = System.getProperty("LOGIN_SERVER");
    private static final String CONTINUE_PARAM      = "continue";
    private static final String NGINX_ADDR_PROPERTY = "NGINX_ADDR";
    private static final String PATH_INFO_PROPERTY  = "PATH_INFO";
    private final String DASHBOARD_HTTPS_PORT = "1443";

    public void doGet( HttpServletRequest req, HttpServletResponse resp ) throws IOException
    {
        LoginCookieUtils.removeCookie(req, resp);
        String login_service_endpoint = "https://" + LOGIN_SERVER + ":" + DASHBOARD_HTTPS_PORT + "/login";
        String continue_url = req.getParameter(CONTINUE_PARAM);
        String redirect_url = login_service_endpoint + "?" + CONTINUE_PARAM + "=" + continue_url;
        redirect_url.replace(":", "%3A");
        redirect_url.replace("?", "%3F");
        redirect_url.replace("=", "%3D");
        resp.sendRedirect(redirect_url);
    }

    public void doPost( HttpServletRequest req, HttpServletResponse resp ) throws IOException
    {}
}
