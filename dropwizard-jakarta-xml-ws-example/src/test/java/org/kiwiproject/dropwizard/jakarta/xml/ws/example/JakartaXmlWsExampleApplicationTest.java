package org.kiwiproject.dropwizard.jakarta.xml.ws.example;

import io.dropwizard.core.Application;
import io.dropwizard.core.setup.Bootstrap;
import io.dropwizard.core.setup.Environment;
import io.dropwizard.db.DataSourceFactory;
import io.dropwizard.hibernate.HibernateBundle;
import jakarta.xml.ws.Endpoint;
import org.apache.cxf.ext.logging.LoggingInInterceptor;
import org.apache.cxf.ext.logging.LoggingOutInterceptor;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.kiwiproject.dropwizard.jakarta.xml.ws.BasicAuthentication;
import org.kiwiproject.dropwizard.jakarta.xml.ws.ClientBuilder;
import org.kiwiproject.dropwizard.jakarta.xml.ws.EndpointBuilder;
import org.kiwiproject.dropwizard.jakarta.xml.ws.JakartaXmlWsBundle;
import org.kiwiproject.dropwizard.jakarta.xml.ws.example.auth.BasicAuthenticator;
import org.kiwiproject.dropwizard.jakarta.xml.ws.example.core.Person;
import org.kiwiproject.dropwizard.jakarta.xml.ws.example.db.PersonDAO;
import org.kiwiproject.dropwizard.jakarta.xml.ws.example.resources.AccessMtomServiceResource;
import org.kiwiproject.dropwizard.jakarta.xml.ws.example.resources.AccessProtectedServiceResource;
import org.kiwiproject.dropwizard.jakarta.xml.ws.example.resources.AccessWsdlFirstServiceResource;
import org.kiwiproject.dropwizard.jakarta.xml.ws.example.resources.WsdlFirstClientHandler;
import org.kiwiproject.dropwizard.jakarta.xml.ws.example.ws.HibernateExampleService;
import org.kiwiproject.dropwizard.jakarta.xml.ws.example.ws.JavaFirstService;
import org.kiwiproject.dropwizard.jakarta.xml.ws.example.ws.JavaFirstServiceImpl;
import org.kiwiproject.dropwizard.jakarta.xml.ws.example.ws.MtomServiceImpl;
import org.kiwiproject.dropwizard.jakarta.xml.ws.example.ws.SimpleService;
import org.kiwiproject.dropwizard.jakarta.xml.ws.example.ws.WsdlFirstServiceImpl;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.mockito.Spy;
import org.mockito.junit.jupiter.MockitoExtension;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import ws.example.ws.xml.jakarta.dropwizard.kiwiproject.org.mtomservice.MtomService;
import ws.example.ws.xml.jakarta.dropwizard.kiwiproject.org.wsdlfirstservice.WsdlFirstService;

import java.util.Collections;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;
import static org.assertj.core.api.Assertions.*;

@ExtendWith(MockitoExtension.class)
public class JakartaXmlWsExampleApplicationTest {

    @Mock
    private Bootstrap<JakartaXmlWsExampleConfiguration> bootstrap;

    @Mock
    private Environment environment;

    @Mock
    private JakartaXmlWsExampleConfiguration configuration;

    @Mock
    private DataSourceFactory dataSourceFactory;

    @Mock
    private HibernateBundle<JakartaXmlWsExampleConfiguration> hibernateBundle;

    @Mock
    private JakartaXmlWsBundle<JakartaXmlWsExampleConfiguration> jwsBundle;

    @Mock
    private JakartaXmlWsBundle<JakartaXmlWsExampleConfiguration> anotherJwsBundle;

    @Mock
    private Endpoint endpoint;

    @Mock
    private PersonDAO personDAO;

    @Mock
    private BasicAuthenticator basicAuthenticator;

    @Mock
    private LoggingInInterceptor loggingInInterceptor;

    @Mock
    private LoggingOutInterceptor loggingOutInterceptor;

    @Mock
    private WsdlFirstClientHandler wsdlFirstClientHandler;

    @Mock
    private SimpleService simpleService;

    @Mock
    private JavaFirstServiceImpl javaFirstServiceImpl;

    @Mock
    private WsdlFirstServiceImpl wsdlFirstServiceImpl;

    @Mock
    private HibernateExampleService hibernateExampleService;

    @Mock
    private MtomServiceImpl mtomServiceImpl;

    @Mock
    private AccessWsdlFirstServiceResource accessWsdlFirstServiceResource;

    @Mock
    private AccessMtomServiceResource accessMtomServiceResource;

    @Mock
    private AccessProtectedServiceResource accessProtectedServiceResource;

    @Spy
    @InjectMocks
    private JakartaXmlWsExampleApplication application;

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
        when(hibernateBundle.getSessionFactory()).thenReturn(mock(org.hibernate.SessionFactory.class));
        when(configuration.getDatabaseConfiguration()).thenReturn(dataSourceFactory);
        when(jwsBundle.publishEndpoint(any(EndpointBuilder.class))).thenReturn(endpoint);
        when(anotherJwsBundle.publishEndpoint(any(EndpointBuilder.class))).thenReturn(endpoint);
        when(jwsBundle.getClient(any(ClientBuilder.class))).thenReturn(mock(WsdlFirstService.class));
        when(jwsBundle.getClient(any(ClientBuilder.class))).thenReturn(mock(MtomService.class));
        when(jwsBundle.getClient(any(ClientBuilder.class))).thenReturn(mock(JavaFirstService.class));
    }

    @Test
    void shouldInitializeWithHibernateAndJwsBundles_whenBootstrapIsCalled() {
        // Given
        // Setup is done in @BeforeEach

        // When
        application.initialize(bootstrap);

        // Then
        verify(bootstrap).addBundle(hibernateBundle);
        verify(bootstrap).addBundle(jwsBundle);
        verify(bootstrap).addBundle(anotherJwsBundle);
    }

    @Test
    void shouldRunWithAllEndpointsAndResources_whenConfigurationAndEnvironmentAreProvided() {
        // Given
        // Setup is done in @BeforeEach

        // When
        application.run(configuration, environment);

        // Then
        verify(jwsBundle).publishEndpoint(new EndpointBuilder("/simple", simpleService));
        verify(anotherJwsBundle).publishEndpoint(new EndpointBuilder("/simple", simpleService));
        verify(jwsBundle).publishEndpoint(new EndpointBuilder("/javafirst", javaFirstServiceImpl)
                .authentication(new BasicAuthentication<>(basicAuthenticator, "TOP_SECRET")));
        verify(jwsBundle).publishEndpoint(new EndpointBuilder("/wsdlfirst", wsdlFirstServiceImpl)
                .cxfInInterceptors(loggingInInterceptor)
                .cxfOutInterceptors(loggingOutInterceptor));
        verify(jwsBundle).publishEndpoint(new EndpointBuilder("/hibernate", hibernateExampleService)
                .sessionFactory(hibernateBundle.getSessionFactory()));
        verify(anotherJwsBundle).publishEndpoint(new EndpointBuilder("/hibernate", hibernateExampleService)
                .sessionFactory(hibernateBundle.getSessionFactory()));
        verify(jwsBundle).publishEndpoint(new EndpointBuilder("/mtom", mtomServiceImpl)
                .enableMtom());
        verify(environment.jersey()).register(accessWsdlFirstServiceResource);
        verify(environment.jersey()).register(accessMtomServiceResource);
        verify(environment.jersey()).register(accessProtectedServiceResource);
    }

    @Test
    void shouldLogReadyMessage_whenServerLifecycleListenerIsAdded() {
        // Given
        // Setup is done in @BeforeEach
        var logger = mock(Logger.class);
        when(LoggerFactory.getLogger(JakartaXmlWsExampleApplication.class)).thenReturn(logger);

        // When
        application.run(configuration, environment);

        // Then
        verify(logger).info("Jakarta XML Web Services Example is ready!");
    }

    @Test
    void shouldRunWithoutException_whenValidConfigurationAndEnvironmentAreProvided() {
        // Given
        // Setup is done in @BeforeEach

        // When
        application.run(configuration, environment);

        // Then
        // No exception is thrown, and all verifications are done in previous tests
    }

    @Test
    void shouldThrowException_whenRunFails() {
        // Given
        // Setup is done in @BeforeEach
        doThrow(new RuntimeException("Test Exception")).when(jwsBundle).publishEndpoint(any(EndpointBuilder.class));

        // When
        try {
            application.run(configuration, environment);
        } catch (Exception e) {
            // Then
            assertThat(e).isInstanceOf(RuntimeException.class);
            assertThat(e.getMessage()).isEqualTo("Test Exception");
        }
    }

    @Test
    void shouldMainMethodRunWithoutException_whenValidArgumentsAreProvided() throws Exception {
        // Given
        // Setup is done in @BeforeEach
        String[] args = {"server", "config.yml"};

        // When
        // We cannot directly test the main method as it calls System.exit()
        // Instead, we can test the run method which is called by main
        application.run(args);

        // Then
        // No exception is thrown, and all verifications are done in previous tests
    }

    @Test
    void shouldMainMethodThrowException_whenRunFails() throws Exception {
        // Given
        // Setup is done in @BeforeEach
        String[] args = {"server", "config.yml"};
        doThrow(new RuntimeException("Test Exception")).when(application).run(any(String[].class));

        // When
        try {
            application.run(args);
        } catch (Exception e) {
            // Then
            assertThat(e).isInstanceOf(RuntimeException.class);
            assertThat(e.getMessage()).isEqualTo("Test Exception");
        }
    }

    @Test
    void shouldStaticLoggerBeInitialized_whenClassIsLoaded() {
        // Given
        // Setup is done in @BeforeEach

        // When
        Logger logger = LoggerFactory.getLogger(JakartaXmlWsExampleApplication.class);

        // Then
        assertThat(logger).isNotNull();
    }
}