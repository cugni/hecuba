#include "TupleRowFactory.h"

/***
 * Builds a tuple factory to retrieve tuples based on rows and keys
 * extracting the information from Cassandra to decide the types to be used
 * @param table_meta Holds the table information
 */
TupleRowFactory::TupleRowFactory(std::shared_ptr<const std::vector<ColumnMeta> > row_info) {
    this->metadata = row_info;
    this->total_bytes = 0;
    if (row_info->end() != row_info->begin()) {
        std::vector<ColumnMeta>::const_iterator last_element = --row_info->end();
        total_bytes = last_element->position + last_element->size;
    }
}



/*** TUPLE BUILDERS ***/

/***
 * Build a tuple taking the given buffer as its internal representation
 * @param data Valid pointer to the values
 * @return TupleRow with the buffer as its inner data
 * @post The TupleRow now owns the data and this cannot be freed
 */
TupleRow *TupleRowFactory::make_tuple(void *data) {
    return new TupleRow(metadata, total_bytes, data);
}

/***
 * Build a tuple from the given Cassandra result row using the factory's metadata
 * @param row Contains the same number of columns than the metadata
 * @return TupleRow with a copy of the values inside the row
 * @post The row can be freed
 */
TupleRow *TupleRowFactory::make_tuple(const CassRow *row) {
    if (!row) return NULL;
    char *buffer = nullptr;

    if (total_bytes > 0) buffer = (char *) malloc(total_bytes);

    TupleRow *new_tuple = new TupleRow(metadata, total_bytes, buffer);

    CassIterator *it = cass_iterator_from_row(row);
    for (uint16_t i = 0; cass_iterator_next(it) && i < metadata->size(); ++i) {
        if (cass_to_c(cass_iterator_get_column(it), buffer + metadata->at(i).position, i) == -1) {
            new_tuple->setNull(i);
        }
    }
    cass_iterator_free(it);
    return new_tuple;
}


/***
 * @pre: -
 * @post: Extract the Cassandra's value from lhs and writes it to the memory pointed by data
 * using the data type information provided by type_array[col]
 * @param lhs Cassandra value
 * @param data Pointer to the place where the extracted value "lhs" should be written
 * @param col Indicates which column, thus, which data type are we processing
 * @return 0 if succeeds
 */
int TupleRowFactory::cass_to_c(const CassValue *lhs, void *data, int16_t col) const {

    if (col < 0 || col >= (int32_t) metadata->size()) {
        throw ModuleException("TupleRowFactory: Cass to C: Asked for column " + std::to_string(col) + " but only " +
                              std::to_string(metadata->size()) + " are present");
    }
    switch (metadata->at(col).type) {
        case CASS_VALUE_TYPE_TEXT:
        case CASS_VALUE_TYPE_VARCHAR:
        case CASS_VALUE_TYPE_ASCII: {
            const char *l_temp;
            size_t l_size;
            CassError rc = cass_value_get_string(lhs, &l_temp, &l_size);
            CHECK_CASS("TupleRowFactory: Cassandra to C parse text unsuccessful, column" + std::to_string(col));
            if (rc == CASS_ERROR_LIB_NULL_VALUE) return -1;
            char *permanent = (char *) malloc(l_size + 1);
            memcpy(permanent, l_temp, l_size);
            permanent[l_size] = '\0';
            memcpy(data, &permanent, sizeof(char *));
            return 0;
        }
        case CASS_VALUE_TYPE_VARINT:
        case CASS_VALUE_TYPE_BIGINT: {
            int64_t *p = static_cast<int64_t * >(data);
            CassError rc = cass_value_get_int64(lhs, p);
            CHECK_CASS(
                    "TupleRowFactory: Cassandra to C parse bigint/varint unsuccessful, column:" + std::to_string(col));
            if (rc == CASS_ERROR_LIB_NULL_VALUE) return -1;
            return 0;
        }
        case CASS_VALUE_TYPE_BLOB: {
            const unsigned char *l_temp;
            size_t l_size;
            CassError rc = cass_value_get_bytes(lhs, &l_temp, &l_size);
            CHECK_CASS("TupleRowFactory: Cassandra to C parse bytes unsuccessful, column:" + std::to_string(col));
            if (rc == CASS_ERROR_LIB_NULL_VALUE) return -1;

            //Allocate space for the bytes
            char *permanent = (char *) malloc(l_size + sizeof(uint64_t));
            //TODO make sure l_size < uint32 max
            uint64_t int_size = (uint64_t) l_size;

            //copy num bytes
            memcpy(permanent, &int_size, sizeof(uint64_t));

            //copy bytes
            memcpy(permanent + sizeof(uint64_t), l_temp, l_size);

            //copy pointer to payload
            memcpy(data, &permanent, sizeof(char *));
            return 0;
        }
        case CASS_VALUE_TYPE_BOOLEAN: {
            cass_bool_t b;
            CassError rc = cass_value_get_bool(lhs, &b);
            CHECK_CASS("TupleRowFactory: Cassandra to C parse bool unsuccessful, column:" + std::to_string(col));
            if (rc == CASS_ERROR_LIB_NULL_VALUE) return -1;
            bool *p = static_cast<bool *>(data);
            if (b == cass_true) *p = true;
            else *p = false;
            return 0;
        }
        case CASS_VALUE_TYPE_COUNTER: {
            CassError rc = cass_value_get_uint32(lhs, reinterpret_cast<uint32_t *>(data));
            CHECK_CASS("TupleRowFactory: Cassandra to C parse counter as uint32 unsuccessful, column:" +
                       std::to_string(col));
            if (rc == CASS_ERROR_LIB_NULL_VALUE) return -1;
            return 0;
        }
        case CASS_VALUE_TYPE_DOUBLE: {
            CassError rc = cass_value_get_double(lhs, reinterpret_cast<double *>(data));
            CHECK_CASS("TupleRowFactory: Cassandra to C parse double unsuccessful, column:" + std::to_string(col));
            if (rc == CASS_ERROR_LIB_NULL_VALUE) return -1;
            return 0;
        }
        case CASS_VALUE_TYPE_FLOAT: {
            CassError rc = cass_value_get_float(lhs, reinterpret_cast<float * >(data));
            CHECK_CASS("TupleRowFactory: Cassandra to C parse float unsuccessful, column:" + std::to_string(col));
            if (rc == CASS_ERROR_LIB_NULL_VALUE) return -1;
            return 0;
        }
        case CASS_VALUE_TYPE_INT: {
            CassError rc = cass_value_get_int32(lhs, reinterpret_cast<int32_t * >(data));
            CHECK_CASS("TupleRowFactory: Cassandra to C parse int32 unsuccessful, column:" + std::to_string(col));
            if (rc == CASS_ERROR_LIB_NULL_VALUE) return -1;
            return 0;
        }
        case CASS_VALUE_TYPE_UUID: {
            CassUuid uuid;
            CassError rc = cass_value_get_uuid(lhs, &uuid);
            uint64_t time_and_version = uuid.time_and_version;
            uint64_t clock_seq_and_node = uuid.clock_seq_and_node;

            CHECK_CASS("TupleRowFactory: Cassandra to C parse UUID unsuccessful, column:" + std::to_string(col));
            if (rc == CASS_ERROR_LIB_NULL_VALUE) return -1;
            char *permanent = (char *) malloc(sizeof(uint64_t) * 2);
            memcpy(permanent, &time_and_version, sizeof(uint64_t));
            memcpy(permanent + sizeof(uint64_t), &clock_seq_and_node, sizeof(uint64_t));
            memcpy(data, &permanent, sizeof(char *));
            return 0;
        }
        case CASS_VALUE_TYPE_SMALL_INT: {
            CassError rc = cass_value_get_int16(lhs, reinterpret_cast<int16_t * >(data));
            CHECK_CASS("TupleRowFactory: Cassandra to C parse int16 unsuccessful, column:" + std::to_string(col));
            if (rc == CASS_ERROR_LIB_NULL_VALUE) return -1;
        }
        case CASS_VALUE_TYPE_TINY_INT: {
            CassError rc = cass_value_get_int8(lhs, reinterpret_cast<int8_t * >(data));
            CHECK_CASS("TupleRowFactory: Cassandra to C parse int16 unsuccessful, column:" + std::to_string(col));
            if (rc == CASS_ERROR_LIB_NULL_VALUE) return -1;
        }
        case CASS_VALUE_TYPE_TUPLE: {
            if (metadata->at(col).pointer->empty())
                throw ModuleException("TupleRowFactory: Cassandra to C parse tuple unsuccessful, tuple is empty");

            TupleRowFactory TFACT = TupleRowFactory(metadata->at(col).pointer);

            void *tuple_data = malloc(TFACT.get_nbytes());

            TupleRow **ptr = (TupleRow **) data;
            *ptr = TFACT.make_tuple(tuple_data);

            CassIterator *tuple_iterator = cass_iterator_from_tuple(lhs);
            if (!tuple_iterator)
                throw ModuleException(
                        "TupleRowFactory: Cassandra to C parse tuple unsuccessful, data type is not tuple");

            /* Iterate over the tuple fields */
            uint32_t j = 0;
            const CassValue *value;
            char *pos_to_copy;
            while (cass_iterator_next(tuple_iterator)) {
                value = cass_iterator_get_value(tuple_iterator);
                pos_to_copy = (char *) tuple_data + metadata->at(col).pointer->at(j).position;
                if (TFACT.cass_to_c(value, pos_to_copy, j) < 0) {
                    TupleRow *inner_data = *ptr;
                    inner_data->setNull(j);
                }
                ++j;
            }
            /* The tuple iterator needs to be freed */
            cass_iterator_free(tuple_iterator);
            return 0;
        }
        case CASS_VALUE_TYPE_DATE: {
            cass_uint32_t year_month_day;
            CassError rc = cass_value_get_uint32(lhs, &year_month_day);
            CHECK_CASS("TupleRowFactory: Cassandra to C parse uint32 unsuccessful, column:" + std::to_string(col));
            if (rc == CASS_ERROR_LIB_NULL_VALUE) return -1;
            int64_t time = (int64_t) cass_date_time_to_epoch(year_month_day, 0);
            memcpy(data, &time, sizeof(int64_t *));
            return 0;
        }
        case CASS_VALUE_TYPE_TIME: {
            cass_int64_t time_of_day;
            CassError rc = cass_value_get_int64(lhs, &time_of_day);
            CHECK_CASS("TupleRowFactory: Cassandra to C parse int64 unsuccessful, column:" + std::to_string(col));
            if (rc == CASS_ERROR_LIB_NULL_VALUE) return -1;
            int64_t time = (int64_t) cass_date_time_to_epoch(0, time_of_day);
            memcpy(data, &time, sizeof(int64_t *));
            return 0;
        }
        case CASS_VALUE_TYPE_DECIMAL:
        case CASS_VALUE_TYPE_TIMESTAMP:
        case CASS_VALUE_TYPE_TIMEUUID:
        case CASS_VALUE_TYPE_INET:
        case CASS_VALUE_TYPE_LIST:
        case CASS_VALUE_TYPE_MAP:
        case CASS_VALUE_TYPE_SET:
        case CASS_VALUE_TYPE_UDT:
        case CASS_VALUE_TYPE_CUSTOM:
        case CASS_VALUE_TYPE_UNKNOWN:
        default:
            throw ModuleException("Default behaviour not supported");
    }
}

void
TupleRowFactory::bind(CassTuple *tuple, const TupleRow *row) const {

    if (!row || !tuple)
        throw ModuleException("Tuple bind: Null tuple received");

    if (metadata->size() != row->n_elem())
        throw ModuleException("Tuple bind: Found " + std::to_string(row->n_elem()) + ", expected " +
                              std::to_string(metadata->size()));

    for (uint16_t bind_pos = 0; bind_pos < row->n_elem(); ++bind_pos) {
        const void *element_i = row->get_element(bind_pos);
        if (element_i != nullptr && !row->isNull(bind_pos)) {
            switch (metadata->at(bind_pos).type) {
                case CASS_VALUE_TYPE_VARCHAR:
                case CASS_VALUE_TYPE_TEXT:
                case CASS_VALUE_TYPE_ASCII: {
                    int64_t *addr = (int64_t *) element_i;
                    const char *d = reinterpret_cast<char *>(*addr);
                    CassError rc = cass_tuple_set_string(tuple, (size_t) bind_pos, d);
                    CHECK_CASS("TupleRowFactory: Cassandra unsuccessful binding Varchar/Text/ASCII to the tuple");
                    break;
                }
                case CASS_VALUE_TYPE_VARINT:
                case CASS_VALUE_TYPE_BIGINT: {
                    int64_t *value = (int64_t *) element_i;
                    CassError rc = cass_tuple_set_int64(tuple, (size_t) bind_pos, *value);
                    CHECK_CASS("TupleRowFactory: Cassandra unsuccessful binding Varint/Bigint to the tuple");
                    break;

                }
                case CASS_VALUE_TYPE_BLOB: {
                    int64_t *value = (int64_t *) element_i;
                    CassError rc = cass_tuple_set_int64(tuple, (size_t) bind_pos, *value);
                    CHECK_CASS("TupleRowFactory: Cassandra unsuccessful binding Blob to the tuple");
                    break;
                }
                case CASS_VALUE_TYPE_BOOLEAN: {
                    cass_bool_t *value = (cass_bool_t *) element_i;
                    CassError rc = cass_tuple_set_int64(tuple, (size_t) bind_pos, *value);
                    CHECK_CASS("TupleRowFactory: Cassandra unsuccessful binding Boolean to tuple");
                    break;
                }
                    //TODO parsed as uint32 or uint64 on different methods
                case CASS_VALUE_TYPE_COUNTER: {
                    int64_t *value = (int64_t *) element_i;
                    CassError rc = cass_tuple_set_int64(tuple, (size_t) bind_pos, *value);
                    CHECK_CASS("TupleRowFactory: Cassandra unsuccessful binding Counter to the tuple");
                    break;
                }
                case CASS_VALUE_TYPE_DOUBLE: {
                    double_t *value = (double_t *) element_i;
                    CassError rc = cass_tuple_set_double(tuple, (size_t) bind_pos, *value);
                    CHECK_CASS("TupleRowFactory: Cassandra unsuccessful binding Double to the tuple");
                    break;
                }
                case CASS_VALUE_TYPE_FLOAT: {
                    float_t *value = (float_t *) element_i;
                    CassError rc = cass_tuple_set_float(tuple, (size_t) bind_pos, *value);
                    CHECK_CASS("TupleRowFactory: Cassandra unsuccessful binding Float to the tuple");
                    break;
                }
                case CASS_VALUE_TYPE_INT: {
                    int32_t *value = (int32_t *) element_i;
                    CassError rc = cass_tuple_set_int32(tuple, (size_t) bind_pos, *value);
                    CHECK_CASS("TupleRowFactory: Cassandra unsuccessful binding Int to the tuple");
                    break;
                }
                case CASS_VALUE_TYPE_UUID: {
                    const uint64_t **uuid = (const uint64_t **) element_i;

                    const uint64_t *time_and_version = *uuid;
                    const uint64_t *clock_seq_and_node = *uuid + 1;

                    CassUuid cass_uuid = {*time_and_version, *clock_seq_and_node};
                    CassError rc = cass_tuple_set_uuid(tuple, (size_t) bind_pos, cass_uuid);
                    CHECK_CASS("TupleRowFactory: Cassandra unsuccessful binding Uuid to the tuple");
                    break;
                }
                case CASS_VALUE_TYPE_SMALL_INT: {
                    int16_t *value = (int16_t *) element_i;
                    CassError rc = cass_tuple_set_int16(tuple, (size_t) bind_pos, *value);
                    CHECK_CASS("TupleRowFactory: Cassandra unsuccessful binding SmallInt to the tuple");
                    break;
                }
                case CASS_VALUE_TYPE_TINY_INT: {
                    int8_t *value = (int8_t *) element_i;
                    CassError rc = cass_tuple_set_int8(tuple, (size_t) bind_pos, *value);
                    CHECK_CASS("TupleRowFactory: Cassandra unsuccessful binding TinyInt to the tuple");
                    break;
                }
                case CASS_VALUE_TYPE_TUPLE: {
                    TupleRow **ptr = (TupleRow **) element_i;
                    const TupleRow *inner_data = *ptr;
                    TupleRowFactory TFACT = TupleRowFactory(metadata->at(bind_pos).pointer);
                    unsigned long n_types = metadata->at(bind_pos).pointer->size();

                    CassTuple *new_tuple = cass_tuple_new(n_types);
                    TFACT.bind(new_tuple, inner_data);
                    CassError rc = cass_tuple_set_tuple(tuple, (size_t) bind_pos, new_tuple);
                    CHECK_CASS("TupleRowFactory: Cassandra unsuccessful binding a new Tuple to the existing tuple");
                    break;
                }
                case CASS_VALUE_TYPE_DATE: {
                    const time_t time = *((time_t *) &element_i);
                    uint32_t year_month_day = cass_date_from_epoch(time);
                    CassError rc = cass_tuple_set_uint32(tuple, (size_t) bind_pos, year_month_day);
                    CHECK_CASS("TupleRowFactory: Cassandra unsuccessful binding int64 to the tuple");
                    break;
                }
                case CASS_VALUE_TYPE_TIME: {
                    const time_t time = *((time_t *) &element_i);
                    cass_int64_t time_of_day = cass_time_from_epoch(time);
                    CassError rc = cass_tuple_set_int64(tuple, (size_t) bind_pos, time_of_day);
                    CHECK_CASS("TupleRowFactory: Cassandra unsuccessful binding int64 to the tuple");
                    break;
                }
                case CASS_VALUE_TYPE_DECIMAL:
                case CASS_VALUE_TYPE_TIMESTAMP:
                case CASS_VALUE_TYPE_TIMEUUID:
                case CASS_VALUE_TYPE_INET:
                case CASS_VALUE_TYPE_LIST:
                case CASS_VALUE_TYPE_MAP:
                case CASS_VALUE_TYPE_SET:
                case CASS_VALUE_TYPE_UDT:
                case CASS_VALUE_TYPE_CUSTOM:
                case CASS_VALUE_TYPE_UNKNOWN:
                default:
                    throw ModuleException("Default behaviour not supported");
            }
        } else {
            //Element is a nullptr
            CassError rc = cass_tuple_set_null(tuple, bind_pos);
            CHECK_CASS("TupleRowFactory: Cassandra binding query unsuccessful [Null value]");
        }
    }
}


void
TupleRowFactory::bind(CassStatement *statement, const TupleRow *row, u_int16_t offset) const {


    if (!row || !statement)
        throw ModuleException("Statement bind: Null tuple row or statement received");

    if (metadata->size() != row->n_elem())
        throw ModuleException("Statement bind: Found " + std::to_string(row->n_elem()) + ", expected " +
                              std::to_string(metadata->size()));

    for (uint16_t i = 0; i < row->n_elem(); ++i) {
        uint16_t bind_pos = offset + i;
        const void *element_i = row->get_element(i);
        if (element_i != nullptr && !row->isNull(i)) {
            switch (metadata->at(i).type) {
                case CASS_VALUE_TYPE_VARCHAR:
                case CASS_VALUE_TYPE_TEXT:
                case CASS_VALUE_TYPE_ASCII: {
                    int64_t *addr = (int64_t *) element_i;
                    const char *d = reinterpret_cast<char *>(*addr);
                    CassError rc = cass_statement_bind_string(statement, bind_pos, d);
                    CHECK_CASS("TupleRowFactory: Cassandra binding query unsuccessful [text], column:" +
                               metadata->at(i).info.begin()->second);
                    break;
                }
                case CASS_VALUE_TYPE_VARINT:
                case CASS_VALUE_TYPE_BIGINT: {
                    const int64_t *data = static_cast<const int64_t *>(element_i);
                    CassError rc = cass_statement_bind_int64(statement, bind_pos,
                                                             *data);//L means long long, K unsigned long long
                    CHECK_CASS("TupleRowFactory: Cassandra binding query unsuccessful [bigint/varint], column:" +
                               metadata->at(i).info.begin()->second);
                    break;
                }
                case CASS_VALUE_TYPE_BLOB: {
                    unsigned char *byte_array;
                    byte_array = *(unsigned char **) element_i;
                    uint64_t *num_bytes = (uint64_t *) byte_array;
                    const unsigned char *bytes = byte_array + sizeof(uint64_t);
                    cass_statement_bind_bytes(statement, bind_pos, bytes, *num_bytes);
                    break;
                }
                case CASS_VALUE_TYPE_BOOLEAN: {
                    cass_bool_t b = cass_false;
                    const bool *bindbool = static_cast<const bool *>(element_i);

                    if (*bindbool) b = cass_true;
                    CassError rc = cass_statement_bind_bool(statement, bind_pos, b);
                    CHECK_CASS("TupleRowFactory: Cassandra binding query unsuccessful [bool], column:" +
                               metadata->at(i).info.begin()->second);
                    break;
                }
                    //TODO parsed as uint32 or uint64 on different methods
                case CASS_VALUE_TYPE_COUNTER: {
                    const uint64_t *data = static_cast<const uint64_t *>(element_i);
                    CassError rc = cass_statement_bind_int64(statement, bind_pos,
                                                             *data);//L means long long, K unsigned long long
                    CHECK_CASS("TupleRowFactory: Cassandra binding query unsuccessful [counter as uint64], column:" +
                               metadata->at(i).info.begin()->second);

                    break;
                }
                case CASS_VALUE_TYPE_DOUBLE: {
                    const double *data = static_cast<const double *>(element_i);
                    CassError rc = cass_statement_bind_double(statement, bind_pos, *data);
                    CHECK_CASS("TupleRowFactory: Cassandra binding query unsuccessful [double], column:" +
                               metadata->at(i).info.begin()->second);

                    break;
                }
                case CASS_VALUE_TYPE_FLOAT: {
                    const float *data = static_cast<const float *>(element_i);

                    CassError rc = cass_statement_bind_float(statement, bind_pos, *data);
                    CHECK_CASS("TupleRowFactory: Cassandra binding query unsuccessful [float], column:" +
                               metadata->at(i).info.begin()->second);

                    break;
                }
                case CASS_VALUE_TYPE_INT: {
                    const int32_t *data = static_cast<const int32_t *>(element_i);

                    CassError rc = cass_statement_bind_int32(statement, bind_pos, *data);
                    CHECK_CASS("TupleRowFactory: Cassandra binding query unsuccessful [int32], column:" +
                               metadata->at(i).info.begin()->second);

                    break;
                }
                case CASS_VALUE_TYPE_UUID: {
                    const uint64_t **uuid = (const uint64_t **) element_i;

                    const uint64_t *time_and_version = *uuid;
                    const uint64_t *clock_seq_and_node = *uuid + 1;

                    CassUuid cass_uuid = {*time_and_version, *clock_seq_and_node};

                    CassError rc = cass_statement_bind_uuid(statement, bind_pos, cass_uuid);
                    CHECK_CASS("TupleRowFactory: Cassandra binding query unsuccessful [UUID], column:" +
                               metadata->at(i).info.begin()->second);

                    break;
                }
                case CASS_VALUE_TYPE_SMALL_INT: {
                    const int16_t *data = static_cast<const int16_t *>(element_i);
                    CassError rc = cass_statement_bind_int16(statement, bind_pos, *data);
                    CHECK_CASS(
                            "TupleRowFactory: Cassandra binding query unsuccessful [small int as int16], column:" +
                            metadata->at(i).info.begin()->second);

                    break;
                }
                case CASS_VALUE_TYPE_TINY_INT: {
                    const int8_t *data = static_cast<const int8_t *>(element_i);
                    CassError rc = cass_statement_bind_int8(statement, bind_pos, *data);
                    CHECK_CASS("TupleRowFactory: Cassandra binding query unsuccessful [tiny int as int8], column:" +
                               metadata->at(i).info.begin()->second);
                    break;
                }
                case CASS_VALUE_TYPE_TUPLE: {
                    TupleRow **ptr = (TupleRow **) element_i;
                    const TupleRow *inner_data = *ptr;
                    TupleRowFactory TFACT = TupleRowFactory(metadata->at(i).pointer);
                    unsigned long n_types = metadata->at(i).pointer->size();
                    CassTuple *tuple = cass_tuple_new(n_types);
                    TFACT.bind(tuple, inner_data);
                    cass_statement_bind_tuple(statement, bind_pos, tuple);
                    cass_tuple_free(tuple);
                    break;
                }
                case CASS_VALUE_TYPE_DATE: {
                    const time_t time = *((time_t *) element_i);
                    cass_uint32_t year_month_day = cass_date_from_epoch(time);
                    CassError rc = cass_statement_bind_uint32(statement, bind_pos, year_month_day);
                    CHECK_CASS("TupleRowFactory: Cassandra binding query unsuccessful [date as int64], column:" +
                               metadata->at(i).info.begin()->second);
                    break;
                }
                case CASS_VALUE_TYPE_TIME: {
                    const time_t time = *((time_t *) &element_i);
                    cass_int64_t time_of_day = cass_time_from_epoch(time);
                    CassError rc = cass_statement_bind_int64(statement, bind_pos, time_of_day);
                    CHECK_CASS("TupleRowFactory: Cassandra binding query unsuccessful [date as int64], column:" +
                               metadata->at(i).info.begin()->second);
                    break;
                }
                case CASS_VALUE_TYPE_DECIMAL:
                case CASS_VALUE_TYPE_TIMESTAMP:
                case CASS_VALUE_TYPE_TIMEUUID:
                case CASS_VALUE_TYPE_INET:
                case CASS_VALUE_TYPE_LIST:
                case CASS_VALUE_TYPE_MAP:
                case CASS_VALUE_TYPE_SET:
                case CASS_VALUE_TYPE_UDT:
                case CASS_VALUE_TYPE_CUSTOM:
                case CASS_VALUE_TYPE_UNKNOWN:
                default:
                    throw ModuleException("Default behaviour not supported");
            }
        } else {
            //Element is a nullptr
            CassError rc = cass_statement_bind_null(statement, bind_pos);
            CHECK_CASS("TupleRowFactory: Cassandra binding query unsuccessful [Null value], column:" +
                       metadata->at(i).info.begin()->second);
        }
    }
}
