package org.kiwiproject.dropwizard.jakarta.xml.ws.example.ws;

import io.dropwizard.hibernate.UnitOfWork;
import jakarta.validation.Valid;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.kiwiproject.dropwizard.jakarta.xml.ws.example.core.Person;
import org.kiwiproject.dropwizard.jakarta.xml.ws.example.db.PersonDAO;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Collections;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class HibernateExampleServiceTest {

    @Mock
    private PersonDAO personDAO;

    @InjectMocks
    private HibernateExampleService hibernateExampleService;

    @BeforeEach
    public void setUp() {
        MockitoAnnotations.openMocks(this);
    }

    @Test
    public void shouldReturnAllPersons_whenGetPersonsIsCalled() {
        // Given
        List<Person> expectedPersons = List.of(new Person(1L, "John Doe"), new Person(2L, "Jane Doe"));
        when(personDAO.findAll()).thenReturn(expectedPersons);

        // When
        List<Person> actualPersons = hibernateExampleService.getPersons();

        // Then
        assertThat(actualPersons).isEqualTo(expectedPersons);
    }

    @Test
    public void shouldReturnEmptyList_whenNoPersonsExist() {
        // Given
        when(personDAO.findAll()).thenReturn(Collections.emptyList());

        // When
        List<Person> actualPersons = hibernateExampleService.getPersons();

        // Then
        assertThat(actualPersons).isEmpty();
    }

    @Test
    public void shouldReturnPerson_whenGetPersonIsCalledWithExistingId() throws HibernateExampleService.PersonNotFoundException {
        // Given
        long personId = 1L;
        Person expectedPerson = new Person(personId, "John Doe");
        when(personDAO.findById(personId)).thenReturn(Optional.of(expectedPerson));

        // When
        Person actualPerson = hibernateExampleService.getPerson(personId);

        // Then
        assertThat(actualPerson).isEqualTo(expectedPerson);
    }

    @Test
    public void shouldThrowPersonNotFoundException_whenGetPersonIsCalledWithNonExistingId() {
        // Given
        long personId = 999L;
        when(personDAO.findById(personId)).thenReturn(Optional.empty());

        // When/Then
        assertThatThrownBy(() -> hibernateExampleService.getPerson(personId))
                .isInstanceOf(HibernateExampleService.PersonNotFoundException.class)
                .hasMessage("Person with id " + personId + " not found");
    }

    @Test
    public void shouldCreatePerson_whenCreatePersonIsCalledWithValidPerson() {
        // Given
        Person personToCreate = new Person(1L, "John Doe");
        Person expectedPerson = new Person(1L, "John Doe");
        when(personDAO.create(personToCreate)).thenReturn(expectedPerson);

        // When
        Person actualPerson = hibernateExampleService.createPerson(personToCreate);

        // Then
        assertThat(actualPerson).isEqualTo(expectedPerson);
    }

    @Test
    public void shouldCreatePersonWithGeneratedId_whenCreatePersonIsCalledWithPersonHavingNoId() {
        // Given
        Person personToCreate = new Person(null, "John Doe");
        Person expectedPerson = new Person(1L, "John Doe");
        when(personDAO.create(personToCreate)).thenReturn(expectedPerson);

        // When
        Person actualPerson = hibernateExampleService.createPerson(personToCreate);

        // Then
        assertThat(actualPerson).isEqualTo(expectedPerson);
    }
}