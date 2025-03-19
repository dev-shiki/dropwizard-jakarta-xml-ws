package org.kiwiproject.dropwizard.jakarta.xml.ws.example.ws;

import jakarta.activation.DataHandler;
import jakarta.mail.util.ByteArrayDataSource;
import org.apache.cxf.helpers.IOUtils;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.mockito.junit.jupiter.MockitoExtension;
import ws.example.ws.xml.jakarta.dropwizard.kiwiproject.org.mtomservice.Hello;
import ws.example.ws.xml.jakarta.dropwizard.kiwiproject.org.mtomservice.HelloResponse;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class MtomServiceImplTest {

    private MtomServiceImpl mtomService;

    @Mock
    private DataHandler mockDataHandler;

    @BeforeEach
    public void setUp() {
        MockitoAnnotations.openMocks(this);
        mtomService = new MtomServiceImpl();
    }

    @Test
    public void shouldReturnHelloResponseWithBinaryData_whenValidHelloRequest() throws IOException {
        // Given
        String title = "Test Title";
        byte[] binaryData = "Test Binary Data".getBytes();
        InputStream inputStream = new ByteArrayInputStream(binaryData);
        DataHandler dataHandler = new DataHandler(new ByteArrayDataSource(inputStream, "application/octet-stream"));

        Hello helloRequest = new Hello();
        helloRequest.setTitle(title);
        helloRequest.setBinary(dataHandler);

        // When
        HelloResponse response = mtomService.hello(helloRequest);

        // Then
        assertThat(response.getTitle()).isEqualTo(title);
        assertThat(response.getBinary().getContentType()).isEqualTo("application/octet-stream");
        assertThat(IOUtils.readBytesFromStream(response.getBinary().getInputStream())).isEqualTo(binaryData);
    }

    @Test
    public void shouldThrowUncheckedIOException_whenIOExceptionDuringReadingInputStream() throws IOException {
        // Given
        String title = "Test Title";
        InputStream inputStream = mock(InputStream.class);
        DataHandler dataHandler = new DataHandler(new ByteArrayDataSource(inputStream, "application/octet-stream"));

        Hello helloRequest = new Hello();
        helloRequest.setTitle(title);
        helloRequest.setBinary(dataHandler);

        when(inputStream.read(any(byte[].class))).thenThrow(new IOException("Mocked IOException"));

        // When/Then
        try {
            mtomService.hello(helloRequest);
        } catch (UncheckedIOException e) {
            assertThat(e.getCause()).isInstanceOf(IOException.class);
            assertThat(e.getCause().getMessage()).isEqualTo("Mocked IOException");
        }
    }

    @Test
    public void shouldReturnHelloResponseWithEmptyBinaryData_whenEmptyInputStream() throws IOException {
        // Given
        String title = "Test Title";
        InputStream inputStream = new ByteArrayInputStream(new byte[0]);
        DataHandler dataHandler = new DataHandler(new ByteArrayDataSource(inputStream, "application/octet-stream"));

        Hello helloRequest = new Hello();
        helloRequest.setTitle(title);
        helloRequest.setBinary(dataHandler);

        // When
        HelloResponse response = mtomService.hello(helloRequest);

        // Then
        assertThat(response.getTitle()).isEqualTo(title);
        assertThat(response.getBinary().getContentType()).isEqualTo("application/octet-stream");
        assertThat(IOUtils.readBytesFromStream(response.getBinary().getInputStream())).isEmpty();
    }

    @Test
    public void shouldReturnHelloResponseWithBinaryData_whenBinaryDataIsLarge() throws IOException {
        // Given
        String title = "Test Title";
        byte[] largeBinaryData = new byte[1024 * 1024]; // 1MB of data
        InputStream inputStream = new ByteArrayInputStream(largeBinaryData);
        DataHandler dataHandler = new DataHandler(new ByteArrayDataSource(inputStream, "application/octet-stream"));

        Hello helloRequest = new Hello();
        helloRequest.setTitle(title);
        helloRequest.setBinary(dataHandler);

        // When
        HelloResponse response = mtomService.hello(helloRequest);

        // Then
        assertThat(response.getTitle()).isEqualTo(title);
        assertThat(response.getBinary().getContentType()).isEqualTo("application/octet-stream");
        assertThat(IOUtils.readBytesFromStream(response.getBinary().getInputStream())).isEqualTo(largeBinaryData);
    }
}