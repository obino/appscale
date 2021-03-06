#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""
Author: Navraj Chohan <nlake44@gmail.com>
Modifications for AppScale
Implementation of Blobstore stub storage based on the datastore

Contains implementation of blobstore_stub.BlobStorage that writes
blobs into the AppScale backends. Blobs are split into chunks of 
1MB segments. 

"""
from google.appengine.api import blobstore
from google.appengine.api.blobstore import MAX_BLOB_FETCH_SIZE
from google.appengine.api.blobstore import blobstore_service_pb, blobstore_stub
from google.appengine.api import datastore, datastore_errors, datastore_types
from google.appengine.ext.blobstore.blobstore import BlobReader
from google.appengine.runtime import apiproxy_errors

__all__ = ['DatastoreBlobStorage']

# The datastore kind used for storing chunks of a blob
_BLOB_CHUNK_KIND_ = "__BlobChunk__"


class DatastoreBlobReader(BlobReader):
  """ A reader that fetches from the datastore instead of the blobstore. """

  @staticmethod
  @datastore.NonTransactional
  def _fetch_data(blob_key, start_index, end_index):
    """ Retrieves a chunk of blob data from datastore entities.

    Args:
      blob_key: A BlobKey used to identify which blob to fetch data from.
      start_index: An integer specifying the start index in bytes of blob data.
      end_index: An integer specifying the end index (inclusive) of blob data.
    Returns:
      A raw bytes string containing the blob data.
    """
    fetch_size = end_index - start_index + 1

    # Get the block we will start from
    block_count = int(start_index / MAX_BLOB_FETCH_SIZE)

    # Get the block's bytes we'll copy
    block_modulo = int(start_index % MAX_BLOB_FETCH_SIZE)

    # This is the last block we'll look at for this request
    block_count_end = int(end_index / MAX_BLOB_FETCH_SIZE)

    block_key = '__'.join([str(blob_key), str(block_count)])
    block_key = datastore.Key.from_path(
      _BLOB_CHUNK_KIND_, block_key, namespace='')

    try:
      block = datastore.Get(block_key)
    except datastore_errors.EntityNotFoundError:
      # If this is the first block, the blob does not exist.
      if block_count == 0:
        raise apiproxy_errors.ApplicationError(
           blobstore_service_pb.BlobstoreServiceError.BLOB_NOT_FOUND)

      # If the first block exists, the index is just past the last block.
      first_block_key = datastore.Key.from_path(
        _BLOB_CHUNK_KIND_, '__'.join([str(blob_key), '0']), namespace='')
      try:
        datastore.Get(first_block_key)
      except datastore_errors.EntityNotFoundError:
        raise apiproxy_errors.ApplicationError(
           blobstore_service_pb.BlobstoreServiceError.BLOB_NOT_FOUND)

      return ''

    data = block['block'][block_modulo:]

    # Matching boundaries, start and end are within one fetch
    if block_count_end == block_count:
      return data[:fetch_size]

    # Must fetch the next block
    block_key = '__'.join([str(blob_key), str(block_count + 1)])
    block_key = datastore.Key.from_path(
      _BLOB_CHUNK_KIND_, block_key, namespace='')

    try:
      block = datastore.Get(block_key)
      data += block['block']
    except datastore_errors.EntityNotFoundError:
      # If the second block is not found, assume the first block was the final
      # block.
      pass

    return data[:fetch_size]

  def _BlobReader__fill_buffer(self, size=0):
    """Fills the internal buffer.

    Args:
      size: Number of bytes to read. Will be clamped to
        [self.__buffer_size, MAX_BLOB_FETCH_SIZE].
    """
    read_size = min(max(size, self._BlobReader__buffer_size),
                    MAX_BLOB_FETCH_SIZE)

    self._BlobReader__buffer = self._fetch_data(
      self._BlobReader__blob_key, self._BlobReader__position,
      self._BlobReader__position + read_size - 1)
    self._BlobReader__buffer_position = 0
    self._BlobReader__eof = len(self._BlobReader__buffer) < read_size


class DatastoreBlobStorage(blobstore_stub.BlobStorage):
  """Storage mechanism for storing blob data in datastore."""

  def __init__(self, app_id):
    """Constructor.

    Args:
      app_id: App id to store blobs on behalf of.
    """
    self._app_id = app_id

  @classmethod
  def _BlobKey(cls, blob_key):
    """Normalize to instance of BlobKey.
 
    Args:
      blob_key: A blob key of a blob to store.
    Returns:
      A normalized blob key of class BlobKey.
    """
    if not isinstance(blob_key, blobstore.BlobKey):
      return blobstore.BlobKey(unicode(blob_key))
    return blob_key

  def StoreBlob(self, blob_key, blob_stream):
    """Store blob stream to the datastore.

    Args:
      blob_key: Blob key of blob to store.
      blob_stream: Stream or stream-like object that will generate blob content.
    """
    block_count = 0
    blob_key_object = self._BlobKey(blob_key)
    while True:
      block = blob_stream.read(blobstore.MAX_BLOB_FETCH_SIZE)
      if not block:
        break
      entity = datastore.Entity(_BLOB_CHUNK_KIND_,
                                name=str(blob_key_object) + "__" + str(block_count), 
                                namespace='')
      entity.update({'block': datastore_types.Blob(block)})
      datastore.Put(entity)
      block_count += 1

  def OpenBlob(self, blob_key):
    """Open blob file for streaming.

    Args:
      blob_key: Blob-key of existing blob to open for reading.

    Returns:
      Open file stream for reading blob from the datastore.
    """
    return DatastoreBlobReader(blob_key, blobstore.MAX_BLOB_FETCH_SIZE, 0)

  @datastore.NonTransactional
  def DeleteBlob(self, blob_key):
    """Delete blob data from the datastore.

    Args:
      blob_key: Blob-key of existing blob to delete.
    Raises:
      ApplicationError: When there is a datastore issue when deleting a blob.
    """
    # Discover all the keys associated with the blob.
    start_key_name = ''.join([str(blob_key), '__'])
    # The chunk key suffixes are all digits, so 'a' is past them.
    end_key_name = ''.join([start_key_name, 'a'])
    start_key = datastore.Key.from_path(_BLOB_CHUNK_KIND_, start_key_name,
                                        namespace='')
    end_key = datastore.Key.from_path(_BLOB_CHUNK_KIND_, end_key_name,
                                      namespace='')
    filters = {'__key__ >': start_key, '__key__ <': end_key}
    query = datastore.Query(filters=filters, keys_only=True)

    keys = list(query.Run())
    datastore.Delete(keys)
